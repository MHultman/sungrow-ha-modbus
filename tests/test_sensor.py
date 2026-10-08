"""Tests for the SunGrow Modbus sensor entities."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.sungrow_modbus.const import SCAN_INTERVAL

from .conftest import seed_inverter, set_u32

PREFIX = "sensor.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "state"),
    [
        ("running_state", "forced_mode"),
        ("mppt1_voltage", "514.8"),
        ("mppt1_current", "5.2"),
        ("mppt1_power", "2677"),
        ("mppt2_power", "700"),
        ("total_dc_power", "3377"),
        ("phase_a_voltage", "230.1"),
        ("phase_b_voltage", "231.2"),
        ("phase_c_voltage", "229.5"),
        ("phase_a_current", "4.8"),
        ("phase_a_power", "1104"),
        ("total_active_power", "3300"),
        ("grid_frequency", "50.01"),
        ("inverter_temperature", "35.2"),
        ("load_power", "1500"),
        ("grid_power", "-677"),
        ("import_power", "0"),
        ("export_power", "677"),
        ("battery_power", "-1200"),
        ("battery_charging_power", "1200"),
        ("battery_discharging_power", "0"),
        ("battery_level", "65.4"),
        ("battery_state_of_health", "99.0"),
        ("battery_capacity", "9.6"),
        # The seeded limits are 5 % and 100 %, the battery 9.6 kWh.
        # 5 + 95 * 65.4 %
        ("battery_level_nominal", "67.1"),
        # 9.6 kWh * 67.1 %
        ("battery_charge_nominal", "6.44"),
        # 9.6 kWh * 95 % * 65.4 %
        ("battery_charge", "5.96"),
        # 5.96 kWh * 99 % health
        ("battery_charge_health_rated", "5.9"),
        ("battery_voltage", "401.2"),
        ("battery_current", "-2.5"),
        ("battery_temperature", "22.1"),
        ("total_backup_power", "330"),
        ("rated_output_power", "8000"),
        ("daily_pv_generation", "25.4"),
        ("total_pv_generation", "51234.5"),
        ("daily_import", "6.0"),
        ("total_import", "25206.1"),
        ("daily_export", "7.0"),
        ("total_export", "15000.0"),
        ("daily_battery_charge", "4.5"),
        ("daily_battery_discharge", "4.0"),
        # 25.4 - 7.0 + 6.0 - 4.5 + 4.0
        ("daily_consumption", "23.9"),
        # 51234.5 - 15000.0 + 25206.1 - 9500.0 + 9000.0
        ("total_consumption", "60940.6"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_states(hass: HomeAssistant, key: str, state: str) -> None:
    """Test sensors show what the registers hold, and what they add up to."""
    assert hass.states.get(f"{PREFIX}_{key}").state == state


@pytest.mark.usefixtures("init_integration")
async def test_entities_per_model(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a two-MPPT three-phase model gets no third or fourth MPPT."""
    assert entity_registry.async_get(f"{PREFIX}_phase_c_voltage") is not None
    assert entity_registry.async_get(f"{PREFIX}_mppt2_power") is not None
    assert entity_registry.async_get(f"{PREFIX}_mppt3_voltage") is None
    assert entity_registry.async_get(f"{PREFIX}_mppt4_voltage") is None


async def test_entities_single_phase_four_mppts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a single-phase four-MPPT model gets its MPPTs and only phase A."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0D1B)  # SH10RS
    mock_modbus_unit.input[5114] = [3801, 45]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    prefix = "sensor.sungrow_sh10rs"
    assert hass.states.get(f"{prefix}_mppt4_voltage").state == "380.1"
    assert hass.states.get(f"{prefix}_mppt4_power").state == "1710"
    # Reads 0xFFFF on a model without it, which is no value at all.
    assert hass.states.get(f"{prefix}_mppt3_voltage").state == STATE_UNKNOWN
    assert entity_registry.async_get(f"{prefix}_phase_a_voltage") is not None
    assert entity_registry.async_get(f"{prefix}_phase_b_voltage") is None


@pytest.mark.usefixtures("init_integration")
async def test_unknown_running_state(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a running state code nobody knows shows as unknown."""
    mock_modbus_unit.input[12999] = 0x7777
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_running_state").state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the meter sensors start disabled, since few setups have the meter."""
    entry = entity_registry.async_get(f"{PREFIX}_meter_active_power")

    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_lifetime_counter_ignores_drops(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a lifetime counter keeps its highest value through a glitch."""
    entity_id = f"{PREFIX}_total_import"

    set_u32(mock_modbus_unit, 13036, 0)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "25206.1"
    assert "lower than the 25206.1 kWh seen before" in caplog.text

    set_u32(mock_modbus_unit, 13036, 252070)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "25207.0"


@pytest.mark.usefixtures("init_integration")
async def test_daily_counter_resets(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a daily counter follows the inverter back to zero at midnight."""
    mock_modbus_unit.input[13035] = 0
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_daily_import").state == "0.0"


async def test_lifetime_counter_restores(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a glitch right after a restart is caught by the restored value."""
    entity_id = f"{PREFIX}_total_import"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "25300.0"),
                {"native_value": 25300.0, "native_unit_of_measurement": "kWh"},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "25300.0"


@pytest.mark.usefixtures("init_integration")
async def test_counters_ignore_not_available(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a counter's "not available" value never reaches the statistics."""
    set_u32(mock_modbus_unit, 13036, 0xFFFFFFFF)
    mock_modbus_unit.input[13035] = 0xFFFF
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The lifetime counter keeps its last real value; today's has none.
    assert hass.states.get(f"{PREFIX}_total_import").state == "25206.1"
    assert hass.states.get(f"{PREFIX}_daily_import").state == STATE_UNKNOWN
    assert hass.states.get(f"{PREFIX}_daily_consumption").state == STATE_UNKNOWN

    set_u32(mock_modbus_unit, 13036, 252070)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_total_import").state == "25207.0"
