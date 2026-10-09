"""Diagnostics support for the SunGrow Modbus integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import SungrowModbusConfigEntry, SungrowModbusDataUpdateCoordinator

TO_REDACT = {CONF_HOST, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SungrowModbusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw words of every block are what it takes to work out a register a
    model reports differently, so they go in as read.
    """
    runtime_data = entry.runtime_data
    inverter = runtime_data.inverter

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "options": dict(entry.options),
        "identity": async_redact_data(asdict(inverter.identity), TO_REDACT),
        "last_poll": {
            label: _last_poll(coordinator)
            for label, coordinator in (
                ("readings", runtime_data.readings),
                ("settings", runtime_data.settings),
            )
        },
        "registers": {
            block.name: {
                "space": block.space,
                "start": block.start,
                "words": inverter.raw.get(block.name),
            }
            for block in (*inverter.reading_blocks, *inverter.setting_blocks)
        },
    }


def _last_poll(coordinator: SungrowModbusDataUpdateCoordinator) -> dict[str, Any]:
    """Return how often a coordinator polls, and what its last poll refreshed."""
    interval = coordinator.update_interval
    seconds = None if interval is None else interval.total_seconds()
    if (report := coordinator.data) is None:
        return {
            "interval": seconds,
            "updated": [],
            "failed": {},
            "error": str(coordinator.last_exception),
        }
    return {
        "interval": seconds,
        "updated": sorted(report.updated),
        "failed": report.failed,
    }
