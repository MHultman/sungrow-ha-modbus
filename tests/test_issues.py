"""Tests for the SunGrow Modbus repair issues."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.sungrow_modbus.const import DOMAIN
from custom_components.sungrow_modbus.helpers import WINET_TIMING
from custom_components.sungrow_modbus.issues import REFUSALS_BEFORE_ISSUE
from custom_components.sungrow_modbus.repairs import BLOCKS_READ

from .conftest import SERIAL_NUMBER, seed_inverter

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


async def _raise_refused_backup_meter(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> str:
    """Set up with the backup meter registers refused until the issue is up."""
    await async_setup_component(hass, "repairs", {})
    mock_modbus_unit.fail_read(
        BACKUP_METER, IllegalDataAddressError(), register_type="input"
    )
    await _setup(hass, entry)
    for _ in range(REFUSALS_BEFORE_ISSUE - 1):
        await _poll(hass, freezer)
    return f"refused_registers_{entry.entry_id}"


def _reading_backup_meter(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> dict[str, er.RegistryEntry]:
    return {
        registry_entry.entity_id: registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if "backup_meter"
        in BLOCKS_READ.get(
            (
                registry_entry.domain,
                registry_entry.unique_id.removeprefix(f"{SERIAL_NUMBER}_"),
            ),
            frozenset(),
        )
    }


async def test_fix_disables_the_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the fix lists and disables the entities, and the block is let be."""
    issue_id = await _raise_refused_backup_meter(
        hass, mock_config_entry, mock_modbus_unit, freezer
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id).is_fixable
    enabled = {
        entity_id
        for entity_id, registry_entry in _reading_backup_meter(
            entity_registry, mock_config_entry
        ).items()
        if registry_entry.disabled_by is None
    }
    assert enabled

    client = await hass_client()
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": issue_id}
    )
    flow = await response.json()
    assert flow["step_id"] == "confirm"
    for entity_id in enabled:
        assert entity_id in flow["description_placeholders"]["entities"]

    response = await client.post(f"/api/repairs/issues/fix/{flow['flow_id']}")
    assert (await response.json())["type"] == "create_entry"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    for entity_id, registry_entry in _reading_backup_meter(
        entity_registry, mock_config_entry
    ).items():
        assert registry_entry.disabled_by is not None, entity_id
    battery_level = entity_registry.async_get(
        "sensor.sungrow_sh8_0rt_v112_battery_level"
    )
    assert battery_level.disabled_by is None

    # Home Assistant reloads the entry for the disabled entities; from then on
    # the block is not read, and the issue does not come back.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_modbus_unit.read_events.clear()
    for _ in range(REFUSALS_BEFORE_ISSUE):
        await _poll(hass, freezer)

    assert all(read.address != BACKUP_METER for read in mock_modbus_unit.read_events)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_fix_with_nothing_left_to_disable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the fix says so when the entities were disabled by hand already."""
    issue_id = await _raise_refused_backup_meter(
        hass, mock_config_entry, mock_modbus_unit, freezer
    )
    for entity_id in _reading_backup_meter(entity_registry, mock_config_entry):
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )

    client = await hass_client()
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": issue_id}
    )

    flow = await response.json()
    assert flow["type"] == "abort"
    assert flow["reason"] == "already_disabled"
