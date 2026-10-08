"""Tests for the SunGrow Modbus switch entities."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.sungrow_modbus.const import SETTINGS_SCAN_INTERVAL

PREFIX = "switch.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "state"),
    [
        ("export_power_limit", STATE_ON),
        ("backup_mode", STATE_OFF),
        ("load_adjustment", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_states(hass: HomeAssistant, key: str, state: str) -> None:
    """Test switches read 0xAA as on and 0x55 as off."""
    assert hass.states.get(f"{PREFIX}_{key}").state == state


@pytest.mark.parametrize(
    ("key", "service", "address", "raw", "state"),
    [
        ("backup_mode", SERVICE_TURN_ON, 13074, 0xAA, STATE_ON),
        ("export_power_limit", SERVICE_TURN_OFF, 13086, 0x55, STATE_OFF),
        ("load_adjustment", SERVICE_TURN_ON, 13010, 0xAA, STATE_ON),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_switch_turn(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    key: str,
    service: str,
    address: int,
    raw: int,
    state: str,
) -> None:
    """Test turning a switch writes 0xAA or 0x55."""
    entity_id = f"{PREFIX}_{key}"

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert mock_modbus_unit.holding[address] == raw
    assert hass.states.get(entity_id).state == state


@pytest.mark.usefixtures("init_integration")
async def test_switch_neither_value(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a register holding neither on nor off shows as unknown."""
    mock_modbus_unit.holding[13074] = 0
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_backup_mode").state == STATE_UNKNOWN
