"""Tests for the SunGrow Modbus diagnostics."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import SERIAL_NUMBER


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics carry the raw registers, but no host or serial number."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics["config_entry"]["host"] == REDACTED
    assert diagnostics["identity"]["serial_number"] == REDACTED
    assert diagnostics["identity"]["model"]["name"] == "SH8.0RT-V112"
    assert diagnostics["options"] == {}
    assert diagnostics["last_poll"]["readings"] == {
        "interval": 10.0,
        "updated": [
            "backup_meter",
            "battery_grid",
            "inverter",
            "meter_bms",
            "system",
        ],
        "failed": {},
    }
    assert diagnostics["last_poll"]["settings"]["failed"] == {}
    assert diagnostics["last_poll"]["settings"]["interval"] == 60.0
    assert diagnostics["registers"]["ems"] == {
        "space": "holding",
        "start": 13049,
        "words": [0, 0xCC, 4200],
    }
    assert diagnostics["registers"]["system"]["start"] == 12999
    assert diagnostics["registers"]["system"]["words"][0] == 0x0800
    assert SERIAL_NUMBER not in str(diagnostics)
