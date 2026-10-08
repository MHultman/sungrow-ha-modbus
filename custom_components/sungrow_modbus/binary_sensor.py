"""Support for SunGrow Modbus binary sensor entities.

The power flow status register is a bit field saying which way energy moves
right now; each bit becomes a binary sensor.
"""

from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SungrowModbusConfigEntry
from .entity import SungrowModbusEntity, SungrowModbusEntityDescription
from .registers import POWER_FLOW_STATUS, SYSTEM, Block

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SungrowModbusBinarySensorEntityDescription(
    BinarySensorEntityDescription, SungrowModbusEntityDescription
):
    """Describes a SunGrow Modbus power flow binary sensor entity."""

    blocks: tuple[Block, ...] = (SYSTEM,)
    bit: int


BINARY_SENSORS: tuple[SungrowModbusBinarySensorEntityDescription, ...] = (
    SungrowModbusBinarySensorEntityDescription(
        key="pv_generating",
        translation_key="pv_generating",
        device_class=BinarySensorDeviceClass.POWER,
        bit=0,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="battery_charging",
        translation_key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        bit=1,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="battery_discharging",
        translation_key="battery_discharging",
        bit=2,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="positive_load_power",
        translation_key="positive_load_power",
        entity_registry_enabled_default=False,
        bit=3,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="exporting",
        translation_key="exporting",
        bit=4,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="importing",
        translation_key="importing",
        bit=5,
    ),
    SungrowModbusBinarySensorEntityDescription(
        key="negative_load_power",
        translation_key="negative_load_power",
        entity_registry_enabled_default=False,
        bit=7,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SungrowModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SunGrow Modbus binary sensor entities based on a config entry."""
    async_add_entities(
        SungrowModbusBinarySensorEntity(entry=entry, description=description)
        for description in BINARY_SENSORS
    )


class SungrowModbusBinarySensorEntity(SungrowModbusEntity, BinarySensorEntity):
    """Defines a SunGrow Modbus power flow binary sensor entity."""

    entity_description: SungrowModbusBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the power flow status has this entity's bit set."""
        status = self.coordinator.inverter.value(POWER_FLOW_STATUS)
        if not isinstance(status, int):
            return None
        return bool(status >> self.entity_description.bit & 1)
