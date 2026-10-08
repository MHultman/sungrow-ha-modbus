"""Support for SunGrow Modbus select entities."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as reg
from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .registers import Register

# Writes go one at a time over the shared link anyway.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SungrowModbusSelectEntityDescription(
    SelectEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus select entity."""

    register: Register
    # The raw value each option writes, and reads back as.
    values: dict[str, int]


def _select(
    key: str,
    register: Register,
    values: dict[str, int],
    entity_category: EntityCategory | None = None,
) -> SungrowModbusSelectEntityDescription:
    return SungrowModbusSelectEntityDescription(
        key=key,
        translation_key=key,
        register=register,
        blocks=(register.block,),
        values=values,
        options=list(values),
        entity_category=entity_category,
    )


SELECTS: tuple[SungrowModbusSelectEntityDescription, ...] = (
    # Microgrid (8) is left out: it is for systems without a grid connection.
    _select(
        "ems_mode",
        reg.EMS_MODE,
        {"self_consumption": 0, "forced": 2, "external_ems": 3, "vpp": 4},
    ),
    # Only acted on while the EMS mode is forced.
    _select(
        "forced_charge_discharge",
        reg.FORCED_CHARGE_DISCHARGE_COMMAND,
        {"stop": 0xCC, "charge": 0xAA, "discharge": 0xBB},
    ),
    # How the inverter drives a load from its DO relay.
    _select(
        "load_adjustment_mode",
        reg.LOAD_ADJUSTMENT_MODE_SELECTION,
        {"timing": 0, "on_off": 1, "power_optimization": 2, "disabled": 3},
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus select entities based on a config entry."""
    if not entry.runtime_data.inverter.identity.model.known:
        return
    async_add_entities(
        SungrowModbusSelectEntity(entry=entry, description=description)
        for description in SELECTS
    )


class SungrowModbusSelectEntity(SungrowModbusEntity, SelectEntity):
    """Defines a SunGrow Modbus select entity."""

    entity_description: SungrowModbusSelectEntityDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option the inverter last reported.

        A value none of the options write, like a mode set from the
        installer's app, shows as unknown rather than as a guess.
        """
        raw = self.coordinator.inverter.value(self.entity_description.register)
        return next(
            (
                option
                for option, value in self.entity_description.values.items()
                if value == raw
            ),
            None,
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the option to the inverter."""
        await self._async_write(
            self.entity_description.register, self.entity_description.values[option]
        )
