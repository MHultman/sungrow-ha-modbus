"""Tests for the SunGrow Modbus number entities."""

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from modbus_connection import (
    IllegalDataValueError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sungrow_modbus.const import CONF_BATTERY_MAX_POWER, DOMAIN

from .conftest import SERIAL_NUMBER, entry_data, seed_inverter, seed_settings

PREFIX = "number.sungrow_sh8_0rt_v112"


async def _set_value(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("key", "state", "minimum", "maximum"),
    [
        ("battery_min_soc", "5.0", 0, 50),
        ("battery_max_soc", "100.0", 50, 100),
        ("battery_reserved_soc_for_backup", "5", 0, 100),
        # Capped by the 8 kW inverter rating, above the 5 kW converter.
        ("battery_forced_charge_discharge_power", "4200", 0, 8000),
        # Already set above every rating, which the range has to include.
        ("battery_max_charge_power", "10600", 10, 10600),
        ("battery_max_discharge_power", "4200", 10, 8000),
        # The range the inverter reports for it.
        ("export_power_limit", "8000", 0, 10000),
        ("battery_charging_start_power", "0", 0, 1000),
        ("battery_discharging_start_power", "190", 0, 1000),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_number_states(
    hass: HomeAssistant, key: str, state: str, minimum: float, maximum: float
) -> None:
    """Test numbers show the settings and the range they take."""
    number = hass.states.get(f"{PREFIX}_{key}")

    assert number.state == state
    assert number.attributes[ATTR_MIN] == minimum
    assert number.attributes[ATTR_MAX] == maximum


@pytest.mark.parametrize(
    ("key", "value", "address", "raw"),
    [
        ("battery_min_soc", 15, 13058, 150),
        ("battery_max_soc", 90, 13057, 900),
        ("battery_reserved_soc_for_backup", 20, 13099, 20),
        ("battery_forced_charge_discharge_power", 3000, 13051, 3000),
        ("battery_max_charge_power", 5000, 33046, 500),
        ("battery_max_discharge_power", 10, 33047, 1),
        ("export_power_limit", 0, 13073, 0),
        ("battery_discharging_start_power", 250, 33149, 25),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_value(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    key: str,
    value: float,
    address: int,
    raw: int,
) -> None:
    """Test setting a number writes the register in the inverter's units."""
    entity_id = f"{PREFIX}_{key}"

    await _set_value(hass, entity_id, value)

    assert mock_modbus_unit.holding[address] == raw
    assert float(hass.states.get(entity_id).state) == value


@pytest.mark.usefixtures("init_integration")
async def test_set_value_moves_derived_sensors(
    hass: HomeAssistant,
) -> None:
    """Test a new SoC limit shows in what is computed from it straight away."""
    await _set_value(hass, f"{PREFIX}_battery_min_soc", 15)

    # 15 + (100 - 15) * 65.4 %
    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_battery_level_nominal").state
        == "70.6"
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_value_out_of_range(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a value outside the range is refused before anything is written."""
    with pytest.raises(ServiceValidationError):
        await _set_value(hass, f"{PREFIX}_battery_min_soc", 60)

    assert mock_modbus_unit.holding[13058] == 50


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (IllegalDataValueError(), "rejected_value"),
        (ModbusConnectionError("gone"), "communication_error"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_value_fails(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    error: Exception,
    translation_key: str,
) -> None:
    """Test a refused or lost write is reported, and the old value stays."""
    mock_modbus_unit.fail_write(13058, error)

    with pytest.raises(HomeAssistantError) as raised:
        await _set_value(hass, f"{PREFIX}_battery_min_soc", 15)

    assert raised.value.translation_key == translation_key
    assert hass.states.get(f"{PREFIX}_battery_min_soc").state == "5.0"


@pytest.mark.parametrize(
    ("device_type_code", "prefix"),
    [
        (0x0D10, "number.sungrow_sh6_0rs"),
        (0x0E20, "number.sungrow_sh5t"),
        (0x0D0C, "number.sungrow_sh5k_30"),
        (0x0D27, "number.sungrow_mg5rl"),
    ],
)
async def test_start_power_only_on_rt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    device_type_code: int,
    prefix: str,
) -> None:
    """Test the undocumented start powers are neither shown nor read off an RT."""
    seed_inverter(mock_modbus_unit, device_type_code=device_type_code)
    seed_settings(mock_modbus_unit)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(f"{prefix}_battery_min_soc") is not None
    assert entity_registry.async_get(f"{prefix}_battery_charging_start_power") is None
    assert all(read.address != 33148 for read in mock_modbus_unit.read_events)


async def test_battery_power_cap(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test the cap from the options limits the three battery power controls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL_NUMBER,
        data=entry_data(),
        options={CONF_BATTERY_MAX_POWER: 5000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for key in (
        "battery_forced_charge_discharge_power",
        "battery_max_charge_power",
        "battery_max_discharge_power",
    ):
        assert hass.states.get(f"{PREFIX}_{key}").attributes[ATTR_MAX] == 5000, key
    # The export limit is not a battery power.
    assert hass.states.get(f"{PREFIX}_export_power_limit").attributes[ATTR_MAX] == 10000

    with pytest.raises(ServiceValidationError):
        await _set_value(hass, f"{PREFIX}_battery_max_charge_power", 6000)
    assert mock_modbus_unit.holding[33046] == 1060


@pytest.mark.usefixtures("init_integration")
async def test_unanswered_write_reads_back(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a write that timed out, but landed, shows what the inverter holds."""
    mock_modbus_unit.fail_write(13058, ModbusTimeoutError("no answer"))
    # The mock raises before storing anything, so the write landing anyway is
    # played by hand.
    mock_modbus_unit.holding[13058] = 150

    with pytest.raises(HomeAssistantError):
        await _set_value(hass, f"{PREFIX}_battery_min_soc", 15)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PREFIX}_battery_min_soc").state == "15.0"
