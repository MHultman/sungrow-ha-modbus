"""Tests for setting up and polling the SunGrow Modbus integration."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sungrow_modbus.const import (
    CONF_CONNECTION,
    CONF_READINGS_INTERVAL,
    CONF_SHOW_UNAVAILABLE,
    CONNECTION_LAN,
    CONNECTION_WINET,
    DOMAIN,
    SETTINGS_SCAN_INTERVAL,
)
from custom_components.sungrow_modbus.helpers import WINET_TIMING

from .conftest import SERIAL_NUMBER, entry_data, seed_inverter


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(WINET_TIMING.readings_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the entry sets up the inverter device, and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Sungrow"
    assert device.model == "SH8.0RT-V112"
    assert device.model_id == "0x0E0E"
    assert device.name == "Sungrow SH8.0RT-V112"
    assert device.serial_number == SERIAL_NUMBER
    assert device.sw_version == "ARM_SAPPHIRE-H_V11_V01_B"

    await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (ModbusConnectionError("refused"), ConfigEntryState.SETUP_RETRY),
        (IllegalDataAddressError(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_probe_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Test a link that is down is retried, and a device that is no Sungrow not."""
    mock_modbus_unit.fail_requests(error)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is state


async def test_setup_wrong_inverter(hass: HomeAssistant) -> None:
    """Test another inverter answering at the address is not taken for this one."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="A0000000000", data=entry_data())
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "wrong_inverter"


@pytest.mark.usefixtures("init_integration")
async def test_poll_retries_a_missed_request(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test one request the WiNet-S drops does not blank the entities."""
    fail_once = [ModbusTimeoutError("dropped")]

    def answer_or_drop() -> list[int]:
        if fail_once:
            raise fail_once.pop()
        return [2301, 2312, 2295]

    # The mock evaluates the callable on the poll's first read, which then
    # times out; the retry reads it again and gets an answer.
    mock_modbus_unit.input[5018] = answer_or_drop
    await _async_poll(hass, freezer)

    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_phase_a_voltage").state == "230.1"
    )


async def _async_setup(hass: HomeAssistant, options: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SERIAL_NUMBER, data=entry_data(), options=options
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# Off by default: the last value read stays up.
SHOWN = pytest.mark.parametrize(
    ("options", "while_down"),
    [({}, None), ({CONF_SHOW_UNAVAILABLE: True}, STATE_UNAVAILABLE)],
)


@SHOWN
async def test_poll_link_down_and_back(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    options: dict[str, Any],
    while_down: str | None,
) -> None:
    """Test what entities show while the link is down, and that they return.

    Connected and Last reading say whether the values are current either way.
    """
    entity_id = "sensor.sungrow_sh8_0rt_v112_battery_level"
    connected = "binary_sensor.sungrow_sh8_0rt_v112_connected"
    last_reading = "sensor.sungrow_sh8_0rt_v112_last_reading"
    await _async_setup(hass, options)
    read_at = hass.states.get(last_reading).state
    assert hass.states.get(connected).state == STATE_ON

    mock_modbus_unit.fail_requests(ModbusConnectionError("gone"))
    await _async_poll(hass, freezer)
    assert hass.states.get(entity_id).state == (while_down or "65.4")
    assert hass.states.get(connected).state == STATE_OFF
    assert hass.states.get(last_reading).state == read_at

    mock_modbus_unit.fail_requests(None)
    await _async_poll(hass, freezer)
    assert hass.states.get(entity_id).state == "65.4"
    assert hass.states.get(connected).state == STATE_ON
    assert hass.states.get(last_reading).state != read_at


@SHOWN
async def test_poll_block_refused(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    options: dict[str, Any],
    while_down: str | None,
) -> None:
    """Test a refused block only touches its own entities."""
    voltage = "sensor.sungrow_sh8_0rt_v112_phase_a_voltage"
    # Phase power needs the voltage too, so it goes with it.
    power = "sensor.sungrow_sh8_0rt_v112_phase_a_power"
    await _async_setup(hass, options)
    before = {
        entity_id: hass.states.get(entity_id).state for entity_id in (voltage, power)
    }

    mock_modbus_unit.fail_read(5002, IllegalDataAddressError(), register_type="input")
    await _async_poll(hass, freezer)

    for entity_id in (voltage, power):
        assert hass.states.get(entity_id).state == (while_down or before[entity_id])
    assert hass.states.get("sensor.sungrow_sh8_0rt_v112_battery_level").state == "65.4"
    assert "the inverter registers did not answer" in caplog.text

    mock_modbus_unit.fail_read(5002, None, register_type="input")
    await _async_poll(hass, freezer)

    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_phase_a_voltage").state == "230.1"
    )
    assert "the inverter registers are answering again" in caplog.text


@SHOWN
async def test_setup_settings_refused(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    options: dict[str, Any],
    while_down: str | None,
) -> None:
    """Test settings the inverter refuses touch only their own controls.

    Never read, they have no last value to keep.
    """
    mock_modbus_unit.fail_read(13049, IllegalDataAddressError())
    entry = await _async_setup(hass, options)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("select.sungrow_sh8_0rt_v112_ems_mode").state == (
        while_down or STATE_UNKNOWN
    )
    assert hass.states.get("number.sungrow_sh8_0rt_v112_battery_min_soc").state == "5.0"


@SHOWN
async def test_setup_settings_unanswered(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    options: dict[str, Any],
    while_down: str | None,
) -> None:
    """Test settings that time out at setup leave the measurements running."""
    fail_settings = [ModbusTimeoutError("dropped")] * 2

    def answer_or_drop() -> int:
        if fail_settings:
            raise fail_settings.pop()
        return 0

    # Readings answer; the first settings read, and its retry, do not.
    mock_modbus_unit.holding[13049] = answer_or_drop
    entry = await _async_setup(hass, options)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.sungrow_sh8_0rt_v112_battery_level").state == "65.4"
    assert hass.states.get("select.sungrow_sh8_0rt_v112_ems_mode").state == (
        while_down or STATE_UNKNOWN
    )


async def test_unknown_model_is_read_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a model nobody knows gets sensors, but no controls and no settings."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0EFF)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entity.domain for entity in entities} == {"sensor", "binary_sensor"}
    assert not any(entity.entity_id.endswith("_nominal") for entity in entities)
    assert all(read.register_type == "input" for read in mock_modbus_unit.read_events)
    assert "set up read-only" in caplog.text


@pytest.mark.parametrize(
    ("connection", "options", "seconds"),
    [
        (CONNECTION_WINET, {}, 10),
        (CONNECTION_LAN, {}, 5),
        (CONNECTION_LAN, {CONF_READINGS_INTERVAL: 30}, 30),
        # Set over the LAN port, then reconfigured to a WiNet-S.
        (CONNECTION_WINET, {CONF_READINGS_INTERVAL: 2}, 5),
    ],
)
async def test_readings_interval(
    hass: HomeAssistant,
    connection: str,
    options: dict[str, int],
    seconds: int,
) -> None:
    """Test the connection sets how often measurements are read, unless set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL_NUMBER,
        data=entry_data(**{CONF_CONNECTION: connection}),
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.readings.update_interval == timedelta(seconds=seconds)
    assert entry.runtime_data.settings.update_interval == SETTINGS_SCAN_INTERVAL
