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

from .const import CONF_CONNECTION, CONF_UNIT_ID, DOMAIN
from .coordinator import (
    SungrowModbusConfigEntry,
    SungrowModbusDataUpdateCoordinator,
    SungrowModbusRuntimeData,
)
from .entity import inverter_device_info
from .helpers import apply_link_timing, create_modbus_params
from .inverter import SungrowConnectionError, SungrowError, SungrowInverter

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


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

    coordinator = SungrowModbusDataUpdateCoordinator(hass, entry, inverter)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SungrowModbusRuntimeData(
        coordinator=coordinator,
        device_info=inverter_device_info(inverter.identity),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SungrowModbusConfigEntry
) -> bool:
    """Unload a SunGrow Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
