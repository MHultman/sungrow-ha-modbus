"""Support for SunGrow Modbus number entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as reg
from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .inverter import SungrowInverter
from .models import Family, InverterModel
from .registers import Register

# Writes go one at a time over the shared link anyway.
PARALLEL_UPDATES = 1

# For an inverter that reports no rating at all, which none should.
FALLBACK_POWER_CEILING = 10_000


@dataclass(frozen=True, kw_only=True)
class SungrowModbusNumberEntityDescription(
    NumberEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus number entity."""

    register: Register
    # Limits the inverter itself reports, where it does.
    min_fn: Callable[[SungrowInverter], float] | None = None
    max_fn: Callable[[SungrowInverter], float] | None = None
    # Whether the battery power cap from the options applies.
    battery_power: bool = False


def _number(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusNumberEntityDescription:
    return SungrowModbusNumberEntityDescription(
        key=key,
        translation_key=key,
        register=register,
        blocks=(register.block,),
        **kwargs,
    )


def _soc(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusNumberEntityDescription:
    return _number(
        key,
        register,
        device_class=NumberDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        **kwargs,
    )


def _power(
    key: str, register: Register, **kwargs: Any
) -> SungrowModbusNumberEntityDescription:
    return _number(
        key,
        register,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_step=10,
        **kwargs,
    )


def _power_ceiling(register: Register) -> Callable[[SungrowInverter], float]:
    """Return the most a battery power setting can sensibly be set to.

    That is what the battery converter or the inverter is rated for, unless
    the setting already holds more: some inverters ship with a charge limit
    above their converter's rating, and the control has to be able to show it.
    """

    def ceiling(inverter: SungrowInverter) -> float:
        candidates = (
            inverter.value(reg.BDC_RATED_POWER),
            inverter.identity.rated_output_power,
            inverter.value(register),
        )
        return max(
            (value for value in candidates if isinstance(value, (int, float))),
            default=FALLBACK_POWER_CEILING,
        )

    return ceiling


def _reported(
    register: Register, fallback: Callable[[SungrowInverter], float]
) -> Callable[[SungrowInverter], float]:
    """Return a limit the inverter reports, or a fallback while it has none."""

    def limit(inverter: SungrowInverter) -> float:
        value = inverter.value(register)
        return value if isinstance(value, (int, float)) else fallback(inverter)

    return limit


def _rated_output(inverter: SungrowInverter) -> float:
    return inverter.identity.rated_output_power or FALLBACK_POWER_CEILING


def _has_start_power(model: InverterModel) -> bool:
    """Return whether a model has the undocumented start power settings."""
    return model.family is Family.RT


NUMBERS: tuple[SungrowModbusNumberEntityDescription, ...] = (
    # Sungrow fixes the ranges: the minimum at or below 50 %, the maximum at or
    # above it, so the two can never cross.
    _soc("min_soc", reg.MIN_SOC, native_min_value=0, native_max_value=50),
    _soc("max_soc", reg.MAX_SOC, native_min_value=50, native_max_value=100),
    _soc(
        "backup_reserve_soc",
        reg.BACKUP_RESERVE_SOC,
        native_min_value=0,
        native_max_value=100,
        entity_category=EntityCategory.CONFIG,
    ),
    _power(
        "forced_charge_discharge_power",
        reg.FORCED_CHARGE_DISCHARGE_POWER,
        native_min_value=0,
        max_fn=_power_ceiling(reg.FORCED_CHARGE_DISCHARGE_POWER),
        battery_power=True,
    ),
    # Sungrow's minimum is 10 W; setting the discharge limit there is how to
    # keep the battery from discharging at all.
    _power(
        "battery_max_charge_power",
        reg.BATTERY_MAX_CHARGE_POWER,
        native_min_value=10,
        max_fn=_power_ceiling(reg.BATTERY_MAX_CHARGE_POWER),
        battery_power=True,
    ),
    _power(
        "battery_max_discharge_power",
        reg.BATTERY_MAX_DISCHARGE_POWER,
        native_min_value=10,
        max_fn=_power_ceiling(reg.BATTERY_MAX_DISCHARGE_POWER),
        battery_power=True,
    ),
    _power(
        "export_power_limit",
        reg.EXPORT_POWER_LIMIT,
        min_fn=_reported(reg.EXPORT_POWER_LIMIT_MIN, lambda _: 0),
        max_fn=_reported(reg.EXPORT_POWER_LIMIT_MAX, _rated_output),
    ),
    _power(
        "battery_charging_start_power",
        reg.BATTERY_CHARGING_START_POWER,
        native_min_value=0,
        native_max_value=1000,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_has_start_power,
    ),
    _power(
        "battery_discharging_start_power",
        reg.BATTERY_DISCHARGING_START_POWER,
        native_min_value=0,
        native_max_value=1000,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_has_start_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus number entities based on a config entry."""
    model = entry.runtime_data.inverter.identity.model
    if not model.known:
        return

    async_add_entities(
        SungrowModbusNumberEntity(entry=entry, description=description)
        for description in NUMBERS
        if description.exists_fn(model)
    )


class SungrowModbusNumberEntity(SungrowModbusEntity, NumberEntity):
    """Defines a SunGrow Modbus number entity."""

    entity_description: SungrowModbusNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setting as the inverter last reported it."""
        value = self.coordinator.inverter.value(self.entity_description.register)
        return value if isinstance(value, (int, float)) else None

    @property
    @override
    def native_min_value(self) -> float:
        """Return the lowest value the setting takes."""
        if (min_fn := self.entity_description.min_fn) is not None:
            return min_fn(self.coordinator.inverter)
        return super().native_min_value

    @property
    @override
    def native_max_value(self) -> float:
        """Return the highest value the setting takes.

        For a battery power, never more than the cap set in the options.
        """
        if (max_fn := self.entity_description.max_fn) is None:
            return super().native_max_value
        ceiling = max_fn(self.coordinator.inverter)
        cap = self._runtime_data.battery_max_power
        if self.entity_description.battery_power and cap is not None:
            return min(ceiling, cap)
        return ceiling

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the setting to the inverter."""
        await self._async_write(self.entity_description.register, value)
