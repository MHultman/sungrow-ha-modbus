"""Tests for the SunGrow Modbus button entities."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest

PREFIX = "button.sungrow_sh8_0rt_v112"


@pytest.mark.parametrize(
    ("key", "command"),
    [("start_inverter", 0xCF), ("stop_inverter", 0xCE)],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
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


@pytest.mark.parametrize("key", ["start_inverter", "stop_inverter"])
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default(
    entity_registry: er.EntityRegistry, key: str
) -> None:
    """Test nobody gets a button that stops production without asking for it."""
    entry = entity_registry.async_get(f"{PREFIX}_{key}")

    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
