"""Tests for setting up and polling the SunGrow Modbus integration."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
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

from custom_components.sungrow_modbus.const import DOMAIN, SCAN_INTERVAL

from .conftest import SERIAL_NUMBER, entry_data


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
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


@pytest.mark.usefixtures("init_integration")
async def test_poll_link_down_and_back(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test every entity goes unavailable while the link is down, and returns."""
    entity_id = "sensor.sungrow_sh8_0rt_v112_battery_level"

    mock_modbus_unit.fail_requests(ModbusConnectionError("gone"))
    await _async_poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_modbus_unit.fail_requests(None)
    await _async_poll(hass, freezer)
    assert hass.states.get(entity_id).state == "65.4"


@pytest.mark.usefixtures("init_integration")
async def test_poll_block_refused(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a refused block only takes its own entities down."""
    mock_modbus_unit.fail_read(5002, IllegalDataAddressError(), register_type="input")
    await _async_poll(hass, freezer)

    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_phase_a_voltage").state
        == STATE_UNAVAILABLE
    )
    # Phase power needs the voltage too, so it goes with it.
    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_phase_a_power").state
        == STATE_UNAVAILABLE
    )
    assert hass.states.get("sensor.sungrow_sh8_0rt_v112_battery_level").state == "65.4"
    assert "the inverter registers did not answer" in caplog.text

    mock_modbus_unit.fail_read(5002, None, register_type="input")
    await _async_poll(hass, freezer)

    assert (
        hass.states.get("sensor.sungrow_sh8_0rt_v112_phase_a_voltage").state == "230.1"
    )
    assert "the inverter registers are answering again" in caplog.text


async def test_setup_settings_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test settings the inverter refuses take only their own controls down."""
    mock_modbus_unit.fail_read(13049, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("select.sungrow_sh8_0rt_v112_ems_mode").state
        == STATE_UNAVAILABLE
    )
    assert hass.states.get("number.sungrow_sh8_0rt_v112_battery_min_soc").state == "5.0"


async def test_setup_settings_unanswered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test settings that time out at setup leave the measurements running."""
    fail_settings = [ModbusTimeoutError("dropped")] * 2

    def answer_or_drop() -> int:
        if fail_settings:
            raise fail_settings.pop()
        return 0

    mock_config_entry.add_to_hass(hass)
    # Readings answer; the first settings read, and its retry, do not.
    mock_modbus_unit.holding[13049] = answer_or_drop

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.sungrow_sh8_0rt_v112_battery_level").state == "65.4"
    assert (
        hass.states.get("select.sungrow_sh8_0rt_v112_ems_mode").state
        == STATE_UNAVAILABLE
    )
