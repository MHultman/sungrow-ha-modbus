"""Repair flows for the SunGrow Modbus integration.

The refused registers issue is fixed by disabling the entities read from
the blocks the inverter refuses. A disabled entity's block is no longer read,
so the issue does not come back; enabling one again reads it again.
"""

from collections.abc import Iterable
from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import probatio

from . import binary_sensor, button, number, select, sensor, switch
from .entity import SungrowModbusEntityDescription

PLATFORMS: tuple[tuple[str, Iterable[SungrowModbusEntityDescription]], ...] = (
    ("binary_sensor", binary_sensor.BINARY_SENSORS),
    ("button", button.BUTTONS),
    ("number", number.NUMBERS),
    ("select", (*select.PRESET_SELECTS, *select.SELECTS)),
    ("sensor", sensor.SENSORS),
    ("switch", switch.SWITCHES),
)

# The blocks each entity reads, by its platform and key.
BLOCKS_READ: dict[tuple[str, str], frozenset[str]] = {
    (platform, description.key): frozenset(block.name for block in description.blocks)
    for platform, descriptions in PLATFORMS
    for description in descriptions
}


def _entities_reading(
    hass: HomeAssistant, entry: ConfigEntry, blocks: frozenset[str]
) -> list[er.RegistryEntry]:
    """Return the enabled entities of an inverter that read any of the blocks."""
    prefix = f"{entry.unique_id}_"
    return [
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registry_entry.disabled_by is None
        and BLOCKS_READ.get(
            (registry_entry.domain, registry_entry.unique_id.removeprefix(prefix)),
            frozenset(),
        )
        & blocks
    ]


class DisableRefusedEntitiesFlow(RepairsFlow):
    """Disables the entities read from registers the inverter refuses."""

    def __init__(self, entry: ConfigEntry, blocks: frozenset[str]) -> None:
        """Initialize the flow for one inverter's refused blocks."""
        self._entry = entry
        self._blocks = blocks

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Start at the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """List the entities, and disable them once the user confirms."""
        entities = _entities_reading(self.hass, self._entry, self._blocks)
        if user_input is not None:
            registry = er.async_get(self.hass)
            for registry_entry in entities:
                registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=er.RegistryEntryDisabler.USER,
                )
            return self.async_create_entry(data={})

        if not entities:
            return self.async_abort(reason="already_disabled")
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "inverter": self._entry.title,
                "blocks": ", ".join(sorted(self._blocks)),
                "entities": "\n".join(
                    f"- `{registry_entry.entity_id}`" for registry_entry in entities
                ),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None]
) -> RepairsFlow:
    """Return the flow that fixes an issue."""
    # The issue is taken back when its inverter is unloaded.
    entry = hass.config_entries.async_get_known_entry(str(data["entry_id"]))
    return DisableRefusedEntitiesFlow(entry, frozenset(str(data["blocks"]).split(",")))
