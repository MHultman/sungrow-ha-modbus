"""Base entity for the SunGrow Modbus integration.

Everything belongs to the one inverter device. Every identity derives from the
inverter's serial number, which the config flow stores as the config entry
unique ID.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SungrowModbusConfigEntry, SungrowModbusDataUpdateCoordinator
from .inverter import Identity
from .models import InverterModel
from .registers import Block


def inverter_name(model: InverterModel) -> str:
    """Return a name for the inverter that reads like one."""
    return f"Sungrow {model.name}"


def inverter_device_info(identity: Identity) -> DeviceInfo:
    """Return device information for the inverter."""
    return DeviceInfo(
        identifiers={(DOMAIN, identity.serial_number)},
        manufacturer="Sungrow",
        model=identity.model.name,
        model_id=f"0x{identity.device_type_code:04X}",
        name=inverter_name(identity.model),
        sw_version=identity.arm_software,
        serial_number=identity.serial_number,
    )


@dataclass(frozen=True, kw_only=True)
class SungrowModbusEntityDescription(EntityDescription):
    """Describes what a SunGrow Modbus entity reads, and on which models."""

    # The blocks the value is decoded from. It is only as fresh as the last of
    # them to answer.
    blocks: tuple[Block, ...]
    exists_fn: Callable[[InverterModel], bool] = lambda _: True


class SungrowModbusEntity(CoordinatorEntity[SungrowModbusDataUpdateCoordinator]):
    """Defines a SunGrow Modbus entity."""

    _attr_has_entity_name = True
    entity_description: SungrowModbusEntityDescription

    def __init__(
        self,
        *,
        entry: SungrowModbusConfigEntry,
        description: SungrowModbusEntityDescription,
    ) -> None:
        """Initialize a SunGrow Modbus entity."""
        super().__init__(coordinator=entry.runtime_data.coordinator)
        self.entity_description = description

        serial_number = entry.unique_id
        if TYPE_CHECKING:
            assert serial_number is not None
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = entry.runtime_data.device_info

    @property
    @override
    def available(self) -> bool:
        """Return whether every block this entity reads answered the last poll.

        An entity that reports a value from an earlier read as if it were
        current is lying about the device.
        """
        failed = self.coordinator.data.failed
        return super().available and not any(
            block.name in failed for block in self.entity_description.blocks
        )
