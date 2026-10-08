"""Support for SunGrow Modbus button entities."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .registers import START_STOP_COMMAND, Block

# Writes go one at a time over the shared link anyway.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SungrowModbusButtonEntityDescription(
    ButtonEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus start or stop button."""

    # The command register is only ever written, never read.
    blocks: tuple[Block, ...] = ()
    command: int


BUTTONS: tuple[SungrowModbusButtonEntityDescription, ...] = (
    SungrowModbusButtonEntityDescription(
        key="start_inverter",
        translation_key="start_inverter",
        entity_category=EntityCategory.CONFIG,
        command=0xCF,
    ),
    SungrowModbusButtonEntityDescription(
        key="stop_inverter",
        translation_key="stop_inverter",
        entity_category=EntityCategory.CONFIG,
        command=0xCE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus button entities based on a config entry."""
    async_add_entities(
        SungrowModbusButtonEntity(entry=entry, description=description)
        for description in BUTTONS
    )


class SungrowModbusButtonEntity(SungrowModbusEntity, ButtonEntity):
    """Defines a SunGrow Modbus start or stop button."""

    entity_description: SungrowModbusButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Send the command to the inverter."""
        await self._async_write(START_STOP_COMMAND, self.entity_description.command)
