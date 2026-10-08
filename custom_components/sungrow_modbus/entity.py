"""Base entity for the SunGrow Modbus integration.

Everything belongs to the one inverter device. Every identity derives from the
inverter's serial number, which the config flow stores as the config entry
unique ID.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SungrowModbusConfigEntry, SungrowModbusDataUpdateCoordinator
from .inverter import Identity, SungrowConnectionError, SungrowRejectedError
from .models import InverterModel
from .registers import Block, Register


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
        self._runtime_data = entry.runtime_data
        super().__init__(
            coordinator=self._runtime_data.coordinator_for(description.blocks)
        )
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
        return super().available and not any(
            self._runtime_data.failed(block) for block in self.entity_description.blocks
        )

    async def _async_write(self, register: Register, value: float) -> None:
        """Write a setting, and show it straight away.

        The inverter acknowledging the write is its confirmation, and the
        written value is what its block holds now. Every entity reading it is
        told at once, measurements computed from it included, rather than
        making the caller wait for the link to read it all back.
        """
        try:
            await self._runtime_data.inverter.async_write(register, value)
        except SungrowConnectionError as err:
            # A write that got no answer may still have landed, so read back
            # what the inverter holds rather than show the old value for a
            # minute. Not awaited: the link is struggling, and the caller
            # should hear about the failure now.
            settings = self._runtime_data.settings
            settings.config_entry.async_create_task(
                self.hass,
                settings.async_request_refresh(),
                "re-read settings after an unanswered write",
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except SungrowRejectedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rejected_value",
                translation_placeholders={"error": str(err)},
            ) from err

        for coordinator in (self._runtime_data.readings, self._runtime_data.settings):
            coordinator.async_update_listeners()
