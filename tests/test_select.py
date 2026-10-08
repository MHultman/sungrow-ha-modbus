"""Tests for the SunGrow Modbus select entities."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.sungrow_modbus.const import SETTINGS_SCAN_INTERVAL

PREFIX = "select.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "state"),
    [
        ("ems_mode", "self_consumption"),
        ("battery_forced_charge_discharge", "stop"),
        ("load_adjustment_mode", "disabled"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_states(hass: HomeAssistant, key: str, state: str) -> None:
    """Test selects show the option the inverter holds."""
    assert hass.states.get(f"{PREFIX}_{key}").state == state


@pytest.mark.parametrize(
    ("key", "option", "address", "raw"),
    [
        ("ems_mode", "forced", 13049, 2),
        ("ems_mode", "external_ems", 13049, 3),
        ("battery_forced_charge_discharge", "charge", 13050, 0xAA),
        ("battery_forced_charge_discharge", "discharge", 13050, 0xBB),
        ("load_adjustment_mode", "power_optimization", 13001, 2),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    key: str,
    option: str,
    address: int,
    raw: int,
) -> None:
    """Test picking an option writes its raw value."""
    entity_id = f"{PREFIX}_{key}"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    assert mock_modbus_unit.holding[address] == raw
    assert hass.states.get(entity_id).state == option


@pytest.mark.usefixtures("init_integration")
async def test_select_unknown_value(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a mode set elsewhere that no option writes shows as unknown."""
    mock_modbus_unit.holding[13049] = 8  # microgrid
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_ems_mode").state == STATE_UNKNOWN
