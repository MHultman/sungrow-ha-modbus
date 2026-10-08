"""Support for Sungrow hybrid inverters over Modbus.

The inverter is a Modbus device. This integration does not own its connection:
it borrows a ``ModbusUnit`` from the ``modbus`` integration, which shares one
connection per device between everything talking to it.
"""

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import (
    CONF_BATTERY_MAX_POWER,
    CONF_CONNECTION,
    CONF_UNIT_ID,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import (
    SungrowModbusConfigEntry,
    SungrowModbusDataUpdateCoordinator,
    SungrowModbusRuntimeData,
)
from .entity import inverter_device_info
from .helpers import apply_link_timing, create_modbus_params
from .inverter import SungrowConnectionError, SungrowError, SungrowInverter

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: SungrowModbusConfigEntry
) -> bool:
    """Set up SunGrow Modbus from a config entry."""
    try:
        unit = async_get_unit(
            hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
        )
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    apply_link_timing(unit, entry.data[CONF_CONNECTION])

    try:
        inverter = await SungrowInverter.async_probe(unit)
    except SungrowConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except SungrowError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_sungrow_inverter",
        ) from err

    # An address can end up pointing at another inverter (a reused DHCP lease),
    # and its measurements are not this one's however the entities are named.
    if inverter.identity.serial_number != entry.unique_id:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="wrong_inverter",
        )

    if not (model := inverter.identity.model).known:
        LOGGER.warning(
            "%s reports a device type code this integration does not know (%s);"
            " it is set up read-only. If it is a Sungrow SH hybrid, please open an"
            " issue with its model name",
            entry.title,
            model.name,
        )

    readings = SungrowModbusDataUpdateCoordinator(
        hass,
        entry,
        inverter,
        blocks=inverter.reading_blocks,
        interval=SCAN_INTERVAL,
    )
    settings = SungrowModbusDataUpdateCoordinator(
        hass,
        entry,
        inverter,
        blocks=inverter.setting_blocks,
        interval=SETTINGS_SCAN_INTERVAL,
    )

    await readings.async_config_entry_first_refresh()
    # The readings already proved the link; settings that refuse one read leave
    # their own controls unavailable instead of failing setup.
    await settings.async_refresh()

    entry.runtime_data = SungrowModbusRuntimeData(
        readings=readings,
        settings=settings,
        device_info=inverter_device_info(inverter.identity),
        battery_max_power=entry.options.get(CONF_BATTERY_MAX_POWER),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SungrowModbusConfigEntry
) -> bool:
    """Unload a SunGrow Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
