"""Tests for the SunGrow Modbus actions."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.restore_state import async_get as async_get_restore_state
from homeassistant.util import dt as dt_util
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
import probatio
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.sungrow_modbus.const import (
    DOMAIN,
    SERVICE_FORCE_BATTERY,
    SETTINGS_SCAN_INTERVAL,
)

from .conftest import seed_inverter

OPERATING_MODE = "select.sungrow_sh8_0rt_v112_operating_mode"

EMS_MODE = 13049
FORCED_COMMAND = 13050
FORCED_POWER = 13051
MAX_DISCHARGE = 33047


async def _force(hass: HomeAssistant, **data: Any) -> None:
    await hass.services.async_call(DOMAIN, SERVICE_FORCE_BATTERY, data, blocking=True)


async def _select(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: OPERATING_MODE, ATTR_OPTION: option},
        blocking=True,
    )


async def _pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_force_charge_then_back(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a forced charge runs for its duration, then self-consumption is back."""
    await _force(hass, mode="charge", power=3000, duration={"minutes": 30})

    assert mock_modbus_unit.holding[FORCED_POWER] == 3000
    assert mock_modbus_unit.holding[EMS_MODE] == 2
    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xAA
    state = hass.states.get(OPERATING_MODE)
    assert state.state == "forced_charge"
    assert state.attributes["forced_until"] == dt_util.utcnow() + timedelta(minutes=30)

    await _pass(hass, freezer, timedelta(minutes=29))
    assert mock_modbus_unit.holding[EMS_MODE] == 2

    await _pass(hass, freezer, timedelta(minutes=1))
    assert mock_modbus_unit.holding[EMS_MODE] == 0
    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xCC
    state = hass.states.get(OPERATING_MODE)
    assert state.state == "self_consumption"
    assert "forced_until" not in state.attributes


async def test_force_names_the_inverter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test the inverter can be named, for more than one set up."""
    await _force(
        hass,
        config_entry_id=init_integration.entry_id,
        mode="discharge",
        duration={"minutes": 5},
    )

    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xBB
    # Left out, the power already set is used.
    assert mock_modbus_unit.holding[FORCED_POWER] == 4200


@pytest.mark.usefixtures("init_integration")
async def test_force_ends_where_it_started(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a forced discharge from "without discharging" goes back to it."""
    await _select(hass, "self_consumption_no_discharge")

    await _force(hass, mode="discharge", duration={"minutes": 10})
    # A discharge held at 10 W would not be one.
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 420

    await _pass(hass, freezer, timedelta(minutes=10))
    assert hass.states.get(OPERATING_MODE).state == "self_consumption_no_discharge"
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 1

    await _select(hass, "self_consumption")
    assert mock_modbus_unit.holding[MAX_DISCHARGE] == 420


@pytest.mark.usefixtures("init_integration")
async def test_new_force_replaces_the_running_one(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a second call sets its own end, and still ends where the first began."""
    await _select(hass, "self_consumption_no_discharge")
    await _force(hass, mode="charge", duration={"minutes": 30})
    await _force(hass, mode="idle", power=9999, duration={"minutes": 10})

    # Idle takes no power, so none is checked or written.
    assert mock_modbus_unit.holding[FORCED_POWER] == 4200
    assert hass.states.get(OPERATING_MODE).state == "battery_bypass"

    await _pass(hass, freezer, timedelta(minutes=10))
    assert hass.states.get(OPERATING_MODE).state == "self_consumption_no_discharge"

    await _pass(hass, freezer, timedelta(minutes=20))
    assert hass.states.get(OPERATING_MODE).state == "self_consumption_no_discharge"


@pytest.mark.usefixtures("init_integration")
async def test_picking_by_hand_cancels_the_end(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an option picked during a forced mode is not undone at its end.

    Picking the same one by hand means keeping it, with no end.
    """
    await _force(hass, mode="charge", duration={"minutes": 10})
    await _select(hass, "forced_charge")

    await _pass(hass, freezer, timedelta(minutes=10))

    assert mock_modbus_unit.holding[EMS_MODE] == 2
    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xAA
    assert "forced_until" not in hass.states.get(OPERATING_MODE).attributes


@pytest.mark.usefixtures("init_integration")
async def test_mode_changed_elsewhere_is_left_be(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a forced mode the inverter already left is not ended over it."""
    await _force(hass, mode="charge", duration={"minutes": 10})
    mock_modbus_unit.holding[EMS_MODE] = 4  # VPP, set in iSolarCloud
    await _pass(hass, freezer, SETTINGS_SCAN_INTERVAL)

    await _pass(hass, freezer, timedelta(minutes=10))

    assert mock_modbus_unit.holding[EMS_MODE] == 4
    assert "forced_until" not in hass.states.get(OPERATING_MODE).attributes


@pytest.mark.usefixtures("init_integration")
async def test_end_is_retried(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an end the inverter does not answer is tried again until it lands."""
    await _force(hass, mode="discharge", duration={"minutes": 10})
    mock_modbus_unit.fail_write(EMS_MODE, ModbusTimeoutError("no answer"))

    await _pass(hass, freezer, timedelta(minutes=10))
    assert mock_modbus_unit.holding[EMS_MODE] == 2
    assert "forced_until" in hass.states.get(OPERATING_MODE).attributes

    mock_modbus_unit.fail_write(EMS_MODE, None)
    await _pass(hass, freezer, timedelta(minutes=1))
    assert mock_modbus_unit.holding[EMS_MODE] == 0


@pytest.mark.usefixtures("init_integration")
async def test_end_is_set_before_anything_is_written(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a force whose write went unanswered, but landed, still ends."""
    mock_modbus_unit.fail_write(FORCED_COMMAND, ModbusTimeoutError("no answer"))
    with pytest.raises(HomeAssistantError):
        await _force(hass, mode="discharge", duration={"minutes": 10})
    # The mock raises before storing anything, so the write landing anyway is
    # played by hand.
    mock_modbus_unit.holding[FORCED_COMMAND] = 0xBB
    mock_modbus_unit.fail_write(FORCED_COMMAND, None)
    await _pass(hass, freezer, SETTINGS_SCAN_INTERVAL)
    assert hass.states.get(OPERATING_MODE).state == "forced_discharge"

    await _pass(hass, freezer, timedelta(minutes=10))

    assert mock_modbus_unit.holding[EMS_MODE] == 0
    assert mock_modbus_unit.holding[FORCED_COMMAND] == 0xCC


@pytest.mark.usefixtures("init_integration")
async def test_end_waits_for_the_settings(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an end is not given up while the settings cannot be read."""
    await _force(hass, mode="discharge", duration={"minutes": 10})
    mock_modbus_unit.fail_read(EMS_MODE, ModbusTimeoutError("no answer"))
    await _pass(hass, freezer, SETTINGS_SCAN_INTERVAL)

    await _pass(hass, freezer, timedelta(minutes=10))
    assert mock_modbus_unit.holding[EMS_MODE] == 2

    # Tried every minute; it lands on the first one after the settings are back.
    mock_modbus_unit.fail_read(EMS_MODE, None)
    await _pass(hass, freezer, SETTINGS_SCAN_INTERVAL)
    await _pass(hass, freezer, timedelta(minutes=1))
    assert mock_modbus_unit.holding[EMS_MODE] == 0


@pytest.mark.parametrize(
    ("minutes_left", "ems_mode"),
    [
        # It ended while Home Assistant was down.
        (-5, 0),
        (5, 2),
    ],
)
async def test_end_survives_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    minutes_left: int,
    ems_mode: int,
) -> None:
    """Test a forced mode set before a restart still ends."""
    mock_modbus_unit.holding[EMS_MODE] = 2
    mock_modbus_unit.holding[FORCED_COMMAND] = 0xAA
    until = dt_util.utcnow() + timedelta(minutes=minutes_left)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(OPERATING_MODE, "forced_charge"),
                {
                    "value": None,
                    "forced": {
                        "option": "forced_charge",
                        "until": until.isoformat(),
                        "resume": "self_consumption",
                    },
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_modbus_unit.holding[EMS_MODE] == ems_mode


@pytest.mark.usefixtures("freezer", "init_integration")
async def test_end_is_stored(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test a running forced mode is what is kept for a restart."""
    await _force(hass, mode="charge", duration={"minutes": 30})

    await async_get_restore_state(hass).async_dump_states()

    stored = next(
        item["extra_data"]
        for item in hass_storage["core.restore_state"]["data"]
        if item["state"]["entity_id"] == OPERATING_MODE
    )
    assert stored["forced"] == {
        "option": "forced_charge",
        "until": (dt_util.utcnow() + timedelta(minutes=30)).isoformat(),
        "resume": "self_consumption",
    }


async def test_stored_end_that_does_not_parse(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a stored end that cannot be read is dropped, not acted on."""
    mock_modbus_unit.holding[EMS_MODE] = 2
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(OPERATING_MODE, "forced_charge"),
                {"value": None, "forced": {"option": "forced_charge", "until": "x"}},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_modbus_unit.holding[EMS_MODE] == 2
    assert "forced_until" not in hass.states.get(OPERATING_MODE).attributes


@pytest.mark.usefixtures("init_integration")
async def test_power_above_the_limit(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test a power above the forced power's limit is refused, and nothing written."""
    with pytest.raises(ServiceValidationError) as raised:
        await _force(hass, mode="charge", power=9000, duration={"minutes": 5})

    assert raised.value.translation_key == "power_above_limit"
    assert raised.value.translation_placeholders == {"power": "9000", "limit": "8000"}
    assert mock_modbus_unit.holding[EMS_MODE] == 0


@pytest.mark.usefixtures("init_integration")
async def test_duration_out_of_range(hass: HomeAssistant) -> None:
    """Test a force is never set for more than a day."""
    with pytest.raises(probatio.Invalid):
        await _force(hass, mode="charge", duration={"hours": 25})


async def test_read_only_inverter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test an inverter set up read-only cannot be forced."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0EFF)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as raised:
        await _force(hass, mode="charge", duration={"minutes": 5})

    assert raised.value.translation_key == "no_operating_mode"


@pytest.mark.usefixtures("init_integration")
async def test_unload_hands_back_the_action(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test an unloaded inverter is not forced through a stale entity."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await _force(
            hass,
            **{ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
            mode="charge",
            duration={"minutes": 5},
        )
