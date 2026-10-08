"""Diagnostics support for the SunGrow Modbus integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import SungrowModbusConfigEntry

TO_REDACT = {CONF_HOST, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SungrowModbusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw words of every block are what it takes to work out a register a
    model reports differently, so they go in as read.
    """
    coordinator = entry.runtime_data.coordinator
    inverter = coordinator.inverter

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "identity": async_redact_data(asdict(inverter.identity), TO_REDACT),
        "last_poll": {
            "updated": sorted(coordinator.data.updated),
            "failed": coordinator.data.failed,
        },
        "registers": {
            block.name: {"start": block.start, "words": inverter.raw.get(block.name)}
            for block in inverter.blocks
        },
    }
