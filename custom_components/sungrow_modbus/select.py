"""Support for SunGrow Modbus select entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import registers as reg
from .coordinator import SungrowModbusConfigEntry, SungrowModbusRuntimeData
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .limits import battery_power_ceiling, capped, rated_output, reported
from .registers import SWITCH_OFF, SWITCH_ON, Register

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


# Microgrid (8) is left out: it is for systems without a grid connection.
EMS_MODES = {"self_consumption": 0, "forced": 2, "external_ems": 3, "vpp": 4}
# Only acted on while the EMS mode is forced.
FORCED_COMMANDS = {"stop": 0xCC, "charge": 0xAA, "discharge": 0xBB}

# The low-level settings the presets below are made of. They stay for what
# the presets do not cover, such as VPP, but out of the way.
SELECTS: tuple[SungrowModbusSelectEntityDescription, ...] = (
    _select("ems_mode", reg.EMS_MODE, EMS_MODES, entity_category=EntityCategory.CONFIG),
    _select(
        "forced_charge_discharge",
        reg.FORCED_CHARGE_DISCHARGE_COMMAND,
        FORCED_COMMANDS,
        entity_category=EntityCategory.CONFIG,
    ),
    # How the inverter drives a load from its DO relay.
    _select(
        "load_adjustment_mode",
        reg.LOAD_ADJUSTMENT_MODE_SELECTION,
        {"timing": 0, "on_off": 1, "power_optimization": 2, "disabled": 3},
        entity_category=EntityCategory.CONFIG,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ParkedSetting:
    """A setting some presets hold at a fixed value, like 10 W of discharge.

    What it held before is remembered, and given back by a preset that needs
    it, so a limit the user set is never lost.
    """

    register: Register
    value: int
    # The most it is given back, and what it gets when nothing was
    # remembered, like when it was parked before Home Assistant saw it.
    ceiling_fn: Callable[[SungrowModbusRuntimeData], float]


@dataclass(frozen=True, kw_only=True)
class Preset:
    """Settings a preset puts the inverter in, and is recognised by."""

    # What the inverter holds while in the preset, written in this order.
    holds: tuple[tuple[Register, int], ...]
    # Written too, but not part of recognising the preset.
    also_writes: tuple[tuple[Register, int], ...] = ()
    # Whether the preset parks the parked setting, needs it given back, or
    # leaves it be.
    parks: bool | None = None


@dataclass(frozen=True, kw_only=True)
class SungrowModbusPresetSelectEntityDescription(
    SelectEntityDescription, SungrowModbusEntityDescription
):
    """Describes a select that sets several settings at once."""

    presets: dict[str, Preset]
    parked: ParkedSetting


def _preset_select(
    key: str, parked: ParkedSetting, presets: dict[str, Preset]
) -> SungrowModbusPresetSelectEntityDescription:
    registers = [parked.register] + [
        register
        for preset in presets.values()
        for register, _ in (*preset.holds, *preset.also_writes)
    ]
    return SungrowModbusPresetSelectEntityDescription(
        key=key,
        translation_key=key,
        blocks=tuple(dict.fromkeys(register.block for register in registers)),
        presets=presets,
        parked=parked,
        options=list(presets),
    )


def _discharge_ceiling(runtime_data: SungrowModbusRuntimeData) -> float:
    ceiling = battery_power_ceiling(reg.BATTERY_MAX_DISCHARGE_POWER)
    return capped(ceiling(runtime_data.inverter), runtime_data.battery_max_power)


def _export_ceiling(runtime_data: SungrowModbusRuntimeData) -> float:
    return reported(reg.EXPORT_POWER_LIMIT_MAX, rated_output)(runtime_data.inverter)


_SELF_CONSUMPTION = ((reg.EMS_MODE, EMS_MODES["self_consumption"]),)
# The command is ignored outside forced mode, but a stale one would be acted
# on the moment forced mode is set by hand.
_STOP = ((reg.FORCED_CHARGE_DISCHARGE_COMMAND, FORCED_COMMANDS["stop"]),)


def _forced(command: str) -> tuple[tuple[Register, int], ...]:
    return (
        (reg.EMS_MODE, EMS_MODES["forced"]),
        (reg.FORCED_CHARGE_DISCHARGE_COMMAND, FORCED_COMMANDS[command]),
    )


# The common setups, each one pick away instead of several settings.
PRESET_SELECTS: tuple[SungrowModbusPresetSelectEntityDescription, ...] = (
    _preset_select(
        "operating_mode",
        # Sungrow's lowest discharge limit, which keeps the battery from
        # discharging at all, in every mode.
        ParkedSetting(
            register=reg.BATTERY_MAX_DISCHARGE_POWER,
            value=10,
            ceiling_fn=_discharge_ceiling,
        ),
        {
            "self_consumption": Preset(
                holds=_SELF_CONSUMPTION, also_writes=_STOP, parks=False
            ),
            "self_consumption_no_discharge": Preset(
                holds=_SELF_CONSUMPTION, also_writes=_STOP, parks=True
            ),
            "battery_bypass": Preset(holds=_forced("stop")),
            "forced_charge": Preset(holds=_forced("charge")),
            "forced_discharge": Preset(holds=_forced("discharge"), parks=False),
        },
    ),
    _preset_select(
        "export_mode",
        ParkedSetting(
            register=reg.EXPORT_POWER_LIMIT, value=0, ceiling_fn=_export_ceiling
        ),
        {
            "no_limit": Preset(holds=((reg.EXPORT_POWER_LIMIT_ENABLED, SWITCH_OFF),)),
            "zero_export": Preset(
                holds=((reg.EXPORT_POWER_LIMIT_ENABLED, SWITCH_ON),), parks=True
            ),
            "limited": Preset(
                holds=((reg.EXPORT_POWER_LIMIT_ENABLED, SWITCH_ON),), parks=False
            ),
        },
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
        [
            *(
                SungrowModbusPresetSelectEntity(entry=entry, description=description)
                for description in PRESET_SELECTS
            ),
            *(
                SungrowModbusSelectEntity(entry=entry, description=description)
                for description in SELECTS
            ),
        ]
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


@dataclass
class RememberedSetting(ExtraStoredData):
    """What a parked setting held before it was parked."""

    value: float | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return the remembered value for storage."""
        return {"value": self.value}


class SungrowModbusPresetSelectEntity(SungrowModbusEntity, SelectEntity, RestoreEntity):
    """Defines a select that sets several settings at once.

    Its option is worked out from what the inverter holds, so a change made
    elsewhere shows, and settings matching no preset show as unknown.
    """

    entity_description: SungrowModbusPresetSelectEntityDescription
    _remembered: float | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Restore what the parked setting held before it was parked."""
        await super().async_added_to_hass()
        if (data := await self.async_get_last_extra_data()) is not None:
            self._remembered = data.as_dict().get("value")

    @property
    @override
    def extra_restore_state_data(self) -> RememberedSetting:
        """Return what to keep across restarts."""
        return RememberedSetting(self._remembered)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the preset the inverter's settings match, if any."""
        return next(
            (
                option
                for option, preset in self.entity_description.presets.items()
                if self._is_in(preset)
            ),
            None,
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the settings of a preset, skipping those already held.

        The parked setting goes first, so a forced discharge never starts
        held at 10 W, and an export limit is in place before it is switched on.
        """
        preset = self.entity_description.presets[option]
        if preset.parks:
            await self._async_park()
        elif preset.parks is False:
            await self._async_unpark()
        for register, value in (*preset.holds, *preset.also_writes):
            if self.coordinator.inverter.value(register) != value:
                await self._async_write(register, value)

    def _is_parked(self) -> bool:
        parked = self.entity_description.parked
        return self.coordinator.inverter.value(parked.register) == parked.value

    def _is_in(self, preset: Preset) -> bool:
        if preset.parks is not None and self._is_parked() != preset.parks:
            return False
        return all(
            self.coordinator.inverter.value(register) == value
            for register, value in preset.holds
        )

    async def _async_park(self) -> None:
        if self._is_parked():
            return
        parked = self.entity_description.parked
        held = self.coordinator.inverter.value(parked.register)
        if isinstance(held, (int, float)):
            self._remembered = held
        await self._async_write(parked.register, parked.value)

    async def _async_unpark(self) -> None:
        if not self._is_parked():
            return
        ceiling = self.entity_description.parked.ceiling_fn(self._runtime_data)
        value = ceiling if self._remembered is None else min(self._remembered, ceiling)
        await self._async_write(self.entity_description.parked.register, value)
        self._remembered = None
