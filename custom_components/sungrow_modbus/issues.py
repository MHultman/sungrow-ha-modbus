"""Repair issues the SunGrow Modbus integration raises.

Neither is persistent: each is raised again by the inverter it is about, so a
restart starts from what the inverter says now, and one the user ignored
stays ignored.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .inverter import Identity, PollReport

DOCS = "https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs"

# A block refused this many polls in a row is taken as one the inverter does
# not have, rather than one that missed a beat.
REFUSALS_BEFORE_ISSUE = 5


def _unknown_model_id(entry: ConfigEntry) -> str:
    return f"unknown_model_{entry.entry_id}"


def _refused_registers_id(entry: ConfigEntry) -> str:
    return f"refused_registers_{entry.entry_id}"


@callback
def async_raise_unknown_model(
    hass: HomeAssistant, entry: ConfigEntry, identity: Identity
) -> None:
    """Tell the user an inverter is set up read-only, or take that back."""
    if identity.model.known:
        ir.async_delete_issue(hass, DOMAIN, _unknown_model_id(entry))
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        _unknown_model_id(entry),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="unknown_model",
        translation_placeholders={
            "inverter": entry.title,
            "code": f"0x{identity.device_type_code:04X}",
        },
        learn_more_url=f"{DOCS}/supported-inverters.md#models-it-does-not-know",
    )


@callback
def async_clear_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Take back every issue about an inverter no longer set up."""
    ir.async_delete_issue(hass, DOMAIN, _unknown_model_id(entry))
    ir.async_delete_issue(hass, DOMAIN, _refused_registers_id(entry))


class RefusedBlocks:
    """Raises one issue for the register blocks an inverter keeps refusing.

    Their entities stay unavailable, which looks like a fault. Most often the
    model or its firmware does not have those registers, and the user can
    disable the entities. A block that answers again is taken off the issue.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the tracker for one inverter."""
        self._hass = hass
        self._entry = entry
        self._refusals: dict[str, int] = {}
        self._raised: frozenset[str] = frozenset()

    @callback
    def record(self, report: PollReport) -> None:
        """Count the blocks a poll was refused, and raise what changed."""
        for block in report.updated:
            self._refusals.pop(block, None)
        for block in report.failed:
            self._refusals[block] = self._refusals.get(block, 0) + 1

        refused = frozenset(
            block
            for block, refusals in self._refusals.items()
            if refusals >= REFUSALS_BEFORE_ISSUE
        )
        if refused == self._raised:
            return
        self._raised = refused
        if not refused:
            ir.async_delete_issue(
                self._hass, DOMAIN, _refused_registers_id(self._entry)
            )
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            _refused_registers_id(self._entry),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="refused_registers",
            translation_placeholders={
                "inverter": self._entry.title,
                "blocks": ", ".join(sorted(refused)),
            },
            learn_more_url=f"{DOCS}/troubleshooting.md#some-entities-never-get-a-value",
        )
