"""Support for SunGrow Modbus switch entities.

Sungrow's on/off settings hold 0xAA while on and 0x55 while off.
"""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as reg
from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .registers import SWITCH_OFF, SWITCH_ON, Register

# Writes go one at a time over the shared link anyway.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SungrowModbusSwitchEntityDescription(
    SwitchEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus switch entity."""

    register: Register


def _switch(
    key: str, register: Register, entity_category: EntityCategory | None = None
) -> SungrowModbusSwitchEntityDescription:
    return SungrowModbusSwitchEntityDescription(
        key=key,
        translation_key=key,
        register=register,
        blocks=(register.block,),
        entity_category=entity_category,
    )


SWITCHES: tuple[SungrowModbusSwitchEntityDescription, ...] = (
    # Holds export to the grid at the export power limit.
    _switch("export_power_limit", reg.EXPORT_POWER_LIMIT_ENABLED),
    # Keeps the backup output powered through a grid outage.
    _switch("backup_mode", reg.BACKUP_MODE),
    # Lets the inverter drive a load from its DO relay.
    _switch(
        "load_adjustment",
        reg.LOAD_ADJUSTMENT_ENABLED,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus switch entities based on a config entry."""
    async_add_entities(
        SungrowModbusSwitchEntity(entry=entry, description=description)
        for description in SWITCHES
    )


class SungrowModbusSwitchEntity(SungrowModbusEntity, SwitchEntity):
    """Defines a SunGrow Modbus switch entity."""

    entity_description: SungrowModbusSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the setting is on, or None if it holds neither."""
        raw = self.coordinator.inverter.value(self.entity_description.register)
        return {SWITCH_ON: True, SWITCH_OFF: False}.get(raw)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._async_write(self.entity_description.register, SWITCH_ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._async_write(self.entity_description.register, SWITCH_OFF)
