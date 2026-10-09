"""Tests for more than one inverter, behind one address with two device IDs."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sungrow_modbus.const import (
    CONF_CONNECTION,
    CONF_UNIT_ID,
    CONNECTION_WINET,
    DOMAIN,
    SERVICE_FORCE_BATTERY,
)
from custom_components.sungrow_modbus.helpers import WINET_TIMING

from .conftest import HOST, PORT, seed_inverter, seed_settings

SECOND_UNIT_ID = 2
SECOND_SERIAL_NUMBER = "A2107654321"

# The same model twice: the second inverter's entity IDs get a suffix.
BATTERY_LEVEL = "sensor.sungrow_sh8_0rt_v112_battery_level"
SECOND_BATTERY_LEVEL = f"{BATTERY_LEVEL}_2"

BATTERY_LEVEL_REGISTER = 13022
EMS_MODE = 13049


@pytest.fixture
def second_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """Return a second inverter, at the same address as the first."""
    unit = mock_modbus_connection.for_unit(SECOND_UNIT_ID)
    seed_inverter(unit, serial_number=SECOND_SERIAL_NUMBER)
    seed_settings(unit)
    unit.input[BATTERY_LEVEL_REGISTER] = 800  # 80.0 %
    return unit


@pytest.fixture
async def second_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry, second_unit: MockModbusUnit
) -> str:
    """Add the second inverter the way a user does, and return its entry ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_CONNECTION: CONNECTION_WINET,
            "more_options": {CONF_UNIT_ID: SECOND_UNIT_ID},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SECOND_SERIAL_NUMBER
    return result["result"].entry_id


async def test_two_inverters_read_their_own_registers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    second_entry: str,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test each inverter gets its own device and entities, with its own values."""
    for entry_id, serial_number in (
        (init_integration.entry_id, init_integration.unique_id),
        (second_entry, SECOND_SERIAL_NUMBER),
    ):
        assert hass.config_entries.async_get_entry(entry_id).state is (
            ConfigEntryState.LOADED
        )
        assert device_registry.async_get_device_by_identifier(
            (DOMAIN, serial_number), entry_id
        )

    assert hass.states.get(BATTERY_LEVEL).state == "65.4"
    assert hass.states.get(SECOND_BATTERY_LEVEL).state == "80.0"


async def test_force_battery_reaches_the_chosen_inverter(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    second_unit: MockModbusUnit,
    second_entry: str,
) -> None:
    """Test the action forces only the inverter it names, and needs one named."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_FORCE_BATTERY,
        {ATTR_CONFIG_ENTRY_ID: second_entry, "mode": "charge", "duration": "00:30"},
        blocking=True,
    )

    assert second_unit.holding[EMS_MODE] == 2
    assert mock_modbus_unit.holding[EMS_MODE] == 0

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_BATTERY,
            {"mode": "charge", "duration": "00:30"},
            blocking=True,
        )


async def test_unloading_one_inverter_leaves_the_other(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    second_unit: MockModbusUnit,
    second_entry: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the other inverter keeps being read after one is unloaded."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    second_unit.input[BATTERY_LEVEL_REGISTER] = 812

    freezer.tick(WINET_TIMING.readings_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(second_entry).state is (
        ConfigEntryState.LOADED
    )
    assert hass.states.get(SECOND_BATTERY_LEVEL).state == "81.2"
