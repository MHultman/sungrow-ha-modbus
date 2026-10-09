"""Tests for the SunGrow Modbus repair issues."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sungrow_modbus.const import DOMAIN
from custom_components.sungrow_modbus.helpers import WINET_TIMING
from custom_components.sungrow_modbus.issues import REFUSALS_BEFORE_ISSUE

from .conftest import seed_inverter

BACKUP_METER = 5722


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(WINET_TIMING.readings_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_unknown_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an inverter set up read-only says so, until it is unloaded."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0EFF)
    await _setup(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"unknown_model_{mock_config_entry.entry_id}"
    )
    assert issue.translation_placeholders == {
        "inverter": "Sungrow SH8.0RT-V112",
        "code": "0x0EFF",
    }

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert not issue_registry.issues


@pytest.mark.usefixtures("init_integration")
async def test_known_model_raises_nothing(issue_registry: ir.IssueRegistry) -> None:
    """Test an inverter the integration knows raises no issue."""
    assert not issue_registry.issues


async def test_refused_registers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test registers refused poll after poll are raised, and taken back."""
    mock_modbus_unit.fail_read(
        BACKUP_METER, IllegalDataAddressError(), register_type="input"
    )
    issue_id = f"refused_registers_{mock_config_entry.entry_id}"
    # Setup's first poll is the first refusal.
    await _setup(hass, mock_config_entry)
    for _ in range(REFUSALS_BEFORE_ISSUE - 2):
        await _poll(hass, freezer)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    await _poll(hass, freezer)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue.translation_placeholders == {
        "inverter": "Sungrow SH8.0RT-V112",
        "blocks": "backup_meter",
    }

    mock_modbus_unit.fail_read(BACKUP_METER, None, register_type="input")
    await _poll(hass, freezer)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_one_answer_starts_the_count_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a block that misses a beat now and then raises nothing."""
    error = IllegalDataAddressError()
    await _setup(hass, mock_config_entry)
    for _ in range(3):
        mock_modbus_unit.fail_read(BACKUP_METER, error, register_type="input")
        for _ in range(REFUSALS_BEFORE_ISSUE - 1):
            await _poll(hass, freezer)
        mock_modbus_unit.fail_read(BACKUP_METER, None, register_type="input")
        await _poll(hass, freezer)

    assert not issue_registry.issues
