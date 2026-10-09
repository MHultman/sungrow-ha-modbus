"""Tests for the SunGrow Modbus config flow."""

from datetime import timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from modbus_connection import IllegalDataAddressError, ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sungrow_modbus.const import (
    CONF_BATTERY_MAX_POWER,
    CONF_CONNECTION,
    CONF_READINGS_INTERVAL,
    CONF_SHOW_UNAVAILABLE,
    CONF_UNIT_ID,
    CONNECTION_LAN,
    CONNECTION_WINET,
    DOMAIN,
)

from .conftest import HOST, PORT, SERIAL_NUMBER, UNIT_ID, entry_data


def _user_input(**overrides: object) -> dict[str, object]:
    """Form input as the sectioned user step submits it."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_CONNECTION: CONNECTION_WINET,
        "more_options": {CONF_UNIT_ID: UNIT_ID},
        **overrides,
    }


async def test_user_flow(hass: HomeAssistant, mock_modbus_unit: MockModbusUnit) -> None:
    """Test setting up an inverter from the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(**{CONF_HOST: " 192.0.2.10 "})
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sungrow SH8.0RT-V112"
    assert result["data"] == entry_data()
    assert result["result"].unique_id == SERIAL_NUMBER
    # The probe asked for WiNet-S patience before talking to it.
    assert mock_modbus_unit.required_connect_delay == 15
    assert mock_modbus_unit.message_spacing == 0.03


async def test_user_flow_lan(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Test the inverter's own LAN port gets no connect delay."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(**{CONF_CONNECTION: CONNECTION_LAN})
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CONNECTION] == CONNECTION_LAN
    assert mock_modbus_unit.required_connect_delay is None


@pytest.mark.parametrize(
    ("error", "address", "reason"),
    [
        (ModbusConnectionError("refused"), None, "cannot_connect"),
        (IllegalDataAddressError(), 4953, "no_sungrow_inverter"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_modbus_unit: MockModbusUnit,
    error: Exception,
    address: int | None,
    reason: str,
) -> None:
    """Test probe failures show on the form, and the flow recovers."""
    if address is None:
        mock_modbus_unit.fail_requests(error)
    else:
        mock_modbus_unit.fail_read(address, error, register_type="input")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_modbus_unit.fail_requests(None)
    mock_modbus_unit.fail_read(4953, None, register_type="input")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an inverter can only be set up once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test pointing the entry at a new address of the same inverter."""
    result = await init_integration.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(**{CONF_HOST: "192.0.2.20"})
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == entry_data(**{CONF_HOST: "192.0.2.20"})


async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test another inverter at the new address is refused."""
    result = await init_integration.start_reconfigure_flow(hass)
    mock_modbus_unit.input[4989] = [0x4130] * 5 + [0] * 5  # serial "A0A0A0A0A0"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input(**{CONF_HOST: "192.0.2.20"})
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert init_integration.data == entry_data()


async def test_options_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting and clearing the battery power cap, which reloads the entry."""
    number = "number.sungrow_sh8_0rt_v112_battery_max_charge_power"

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_BATTERY_MAX_POWER: 5000}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {CONF_BATTERY_MAX_POWER: 5000}
    assert hass.states.get(number).attributes["max"] == 5000

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert init_integration.options == {}
    assert hass.states.get(number).attributes["max"] == 10600


async def test_options_readings_interval(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the measurement interval, shown with the connection's own limits."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["description_placeholders"] == {"default": "10", "minimum": "5"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_READINGS_INTERVAL: 30}
    )
    await hass.async_block_till_done()

    assert init_integration.options == {CONF_READINGS_INTERVAL: 30}
    assert init_integration.runtime_data.readings.update_interval == timedelta(
        seconds=30
    )


async def test_options_readings_interval_default_left_unset(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the default is not stored, so it follows a reconfigured connection."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_READINGS_INTERVAL: 10}
    )
    await hass.async_block_till_done()

    assert init_integration.options == {}


async def test_options_readings_interval_below_minimum(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a WiNet-S cannot be polled faster than it keeps up with."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_READINGS_INTERVAL: 3}
        )


@pytest.mark.parametrize(
    ("show_unavailable", "options"),
    [(True, {CONF_SHOW_UNAVAILABLE: True}), (False, {})],
)
async def test_options_show_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    show_unavailable: bool,
    options: dict[str, bool],
) -> None:
    """Test entities can be set to go unavailable; off is the default, not stored."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SHOW_UNAVAILABLE: show_unavailable}
    )
    await hass.async_block_till_done()

    assert init_integration.options == options
    assert init_integration.runtime_data.show_unavailable is show_unavailable
