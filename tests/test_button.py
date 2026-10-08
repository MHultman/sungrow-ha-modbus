"""Tests for the SunGrow Modbus button entities."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest

PREFIX = "button.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "command"),
    [("start_inverter", 0xCF), ("stop_inverter", 0xCE)],
)
@pytest.mark.usefixtures("init_integration")
async def test_press(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit, key: str, command: int
) -> None:
    """Test each button writes its command to the start/stop register."""
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"{PREFIX}_{key}"},
        blocking=True,
    )

    assert [(write.address, write.values) for write in writes] == [(12999, [command])]
