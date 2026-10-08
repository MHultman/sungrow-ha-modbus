"""Tests for the SunGrow Modbus preset selects."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from modbus_connection import IllegalDataValueError
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.sungrow_modbus.const import (
    CONF_BATTERY_MAX_POWER,
    DOMAIN,
    SETTINGS_SCAN_INTERVAL,
)

from .conftest import SERIAL_NUMBER, entry_data

PREFIX = "select.sungrow_sh8_0rt_v112"
OPERATING_MODE = f"{PREFIX}_operating_mode"
EXPORT_MODE = f"{PREFIX}_export_mode"

EMS_MODE = 13049
FORCED_COMMAND = 13050
MAX_DISCHARGE = 33047
EXPORT_LIMIT = 13073
EXPORT_LIMIT_SWITCH = 13086

# Raw values: the discharge limit is in steps of 10 W.
PARKED_DISCHARGE = 1
SEEDED_DISCHARGE = 420


async def _select(hass: HomeAssistant, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )


async def _poll_settings(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SETTINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_preset_states(hass: HomeAssistant) -> None:
    """Test the presets show what the seeded inverter holds."""
    assert hass.states.get(OPERATING_MODE).state == "self_consumption"
    assert hass.states.get(EXPORT_MODE).state == "limited"


@pytest.mark.parametrize(
    ("option", "ems_mode", "command", "discharge"),
    [
        ("self_consumption_no_discharge", 0, 0xCC, PARKED_DISCHARGE),
        ("battery_bypass", 2, 0xCC, SEEDED_DISCHARGE),
        ("forced_charge", 2, 0xAA, SEEDED_DISCHARGE),
        ("forced_discharge", 2, 0xBB, SEEDED_DISCHARGE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_operating_mode(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    option: str,
    ems_mode: int,
    command: int,
    discharge: int,
) -> None:
    """Test each operating mode writes its settings, and is then shown."""
    await _select(hass, OPERATING_MODE, option)

    assert mock_modbus_unit.holding[EMS_MODE] == ems_mode
    assert mock_modbus_unit.holding[FORCED_COMMAND] == command
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == discharge
    assert hass.states.get(OPERATING_MODE).state == option


@pytest.mark.usefixtures("init_integration")
async def test_settings_already_held_are_not_written(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test picking a preset writes only what it changes, mode first."""
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)

    await _select(hass, OPERATING_MODE, "self_consumption")
    await _select(hass, OPERATING_MODE, "forced_charge")

    assert [(write.address, write.values) for write in writes] == [
        (EMS_MODE, [2]),
        (FORCED_COMMAND, [0xAA]),
    ]


@pytest.mark.usefixtures("init_integration")
async def test_discharge_limit_is_given_back(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test leaving "without discharging" gives back the user's own limit."""
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == SEEDED_DISCHARGE
    assert hass.states.get(OPERATING_MODE).state == "self_consumption"


@pytest.mark.usefixtures("init_integration")
async def test_parking_twice_keeps_the_limit(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test picking "without discharging" again does not remember 10 W."""
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == SEEDED_DISCHARGE


@pytest.mark.usefixtures("init_integration")
async def test_limit_given_back_is_forgotten(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a limit is given back once, not again after 10 W is set elsewhere."""
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    await _select(hass, OPERATING_MODE, "self_consumption")
    mock_modbus_unit.holding[MAX_DISCHARGE] = PARKED_DISCHARGE
    await _poll_settings(hass, freezer)

    await _select(hass, OPERATING_MODE, "self_consumption")

    # The inverter's 8000 W rating, not the 4200 W given back before.
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 800


@pytest.mark.usefixtures("init_integration")
async def test_forced_discharge_is_not_held_at_10_w(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a forced discharge gets the discharge limit back before it starts."""
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)

    await _select(hass, OPERATING_MODE, "forced_discharge")

    assert [write.address for write in writes] == [
        MAX_DISCHARGE,
        EMS_MODE,
        FORCED_COMMAND,
    ]
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == SEEDED_DISCHARGE


@pytest.mark.usefixtures("init_integration")
async def test_forced_charge_keeps_the_battery_from_discharging(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a forced charge leaves the discharge limit as it is."""
    await _select(hass, OPERATING_MODE, "self_consumption_no_discharge")
    await _select(hass, OPERATING_MODE, "forced_charge")
    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == SEEDED_DISCHARGE


async def test_discharge_limit_survives_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test the limit remembered before a restart is the one given back."""
    mock_modbus_unit.holding[MAX_DISCHARGE] = PARKED_DISCHARGE
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(OPERATING_MODE, "self_consumption_no_discharge"),
                {"value": 3000},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 300


@pytest.mark.parametrize(
    ("options", "discharge"),
    [
        # The inverter's 8000 W rating is above the 5000 W converter's.
        ({}, 800),
        ({CONF_BATTERY_MAX_POWER: 5000}, 500),
    ],
)
async def test_discharge_limit_with_nothing_remembered(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    options: dict[str, int],
    discharge: int,
) -> None:
    """Test a limit parked before Home Assistant saw it goes to the ceiling."""
    mock_modbus_unit.holding[MAX_DISCHARGE] = PARKED_DISCHARGE
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SERIAL_NUMBER, data=entry_data(), options=options
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(OPERATING_MODE).state == "self_consumption_no_discharge"

    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == discharge


async def test_remembered_limit_held_to_the_cap(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a remembered limit above a cap set since is given back at the cap."""
    mock_modbus_unit.holding[MAX_DISCHARGE] = PARKED_DISCHARGE
    mock_restore_cache_with_extra_data(
        hass,
        [(State(OPERATING_MODE, "self_consumption_no_discharge"), {"value": 7000})],
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL_NUMBER,
        data=entry_data(),
        options={CONF_BATTERY_MAX_POWER: 5000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await _select(hass, OPERATING_MODE, "self_consumption")

    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 500


@pytest.mark.usefixtures("init_integration")
async def test_settings_matching_no_preset(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test settings made elsewhere that match no preset show as unknown."""
    mock_modbus_unit.holding[EMS_MODE] = 4  # VPP
    await _poll_settings(hass, freezer)

    assert hass.states.get(OPERATING_MODE).state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_refused_write_stops_the_preset(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a refused setting is reported and nothing after it is written."""
    mock_modbus_unit.fail_write(EMS_MODE, IllegalDataValueError())

    with pytest.raises(HomeAssistantError):
        await _select(hass, OPERATING_MODE, "forced_discharge")

    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xCC
    assert hass.states.get(OPERATING_MODE).state == "self_consumption"


@pytest.mark.usefixtures("init_integration")
async def test_export_mode(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test zero export parks the limit, and limited gives it back."""
    await _select(hass, EXPORT_MODE, "zero_export")
    assert mock_modbus_unit.holding[EXPORT_LIMIT] == 0
    assert mock_modbus_unit.holding[EXPORT_LIMIT_SWITCH] == 0xAA
    assert hass.states.get(EXPORT_MODE).state == "zero_export"

    await _select(hass, EXPORT_MODE, "no_limit")
    assert mock_modbus_unit.holding[EXPORT_LIMIT] == 0
    assert mock_modbus_unit.holding[EXPORT_LIMIT_SWITCH] == 0x55
    assert hass.states.get(EXPORT_MODE).state == "no_limit"

    await _select(hass, EXPORT_MODE, "limited")
    assert mock_modbus_unit.holding[EXPORT_LIMIT] == 8000
    assert mock_modbus_unit.holding[EXPORT_LIMIT_SWITCH] == 0xAA
    assert hass.states.get(EXPORT_MODE).state == "limited"


async def test_export_limit_with_nothing_remembered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test limited with no limit to give back goes to the inverter's maximum."""
    mock_modbus_unit.holding[EXPORT_LIMIT] = 0
    mock_modbus_unit.holding[EXPORT_LIMIT_SWITCH] = 0x55
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _select(hass, EXPORT_MODE, "limited")

    assert mock_modbus_unit.holding[EXPORT_LIMIT] == 10000
    assert mock_modbus_unit.holding[EXPORT_LIMIT_SWITCH] == 0xAA


@pytest.mark.parametrize("key", ["ems_mode", "battery_forced_charge_discharge"])
@pytest.mark.usefixtures("init_integration")
async def test_low_level_selects_are_configuration(
    entity_registry: er.EntityRegistry, key: str
) -> None:
    """Test the settings the presets are made of stay out of the way."""
    entry = entity_registry.async_get(f"{PREFIX}_{key}")
    assert entry.entity_category is EntityCategory.CONFIG
