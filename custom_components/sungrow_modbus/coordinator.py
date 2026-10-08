"""DataUpdateCoordinators for the SunGrow Modbus integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER
from .inverter import PollReport, SungrowConnectionError, SungrowInverter
from .registers import Block

if TYPE_CHECKING:
    from .select import SungrowModbusOperatingModeSelectEntity

type SungrowModbusConfigEntry = ConfigEntry[SungrowModbusRuntimeData]


class SungrowModbusDataUpdateCoordinator(DataUpdateCoordinator[PollReport]):
    """Polls one set of the inverter's register blocks over Modbus.

    A poll can come back partial: a block the inverter refuses only takes its
    own entities down. The report names what refreshed, which is what entities
    read their availability from.
    """

    config_entry: SungrowModbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SungrowModbusConfigEntry,
        inverter: SungrowInverter,
        *,
        blocks: tuple[Block, ...],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.inverter = inverter
        self.blocks = blocks
        self._silent: set[str] = set()
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )

    @override
    async def _async_update_data(self) -> PollReport:
        """Poll the inverter, reporting what answered."""
        try:
            report = await self._async_poll_with_retry()
        except SungrowConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._log_silence(report)
        return report

    async def _async_poll_with_retry(self) -> PollReport:
        """Poll, giving a link that dropped one request a second chance.

        The WiNet-S misses a request now and then. Blanking every entity for a
        whole interval over one of those would leave gaps in every graph.
        """
        try:
            return await self.inverter.async_update(self.blocks)
        except SungrowConnectionError as err:
            LOGGER.debug("%s: nothing answered (%s); polling again", self.name, err)

        return await self.inverter.async_update(self.blocks)

    def _log_silence(self, report: PollReport) -> None:
        """Log a block falling silent once, and log its return."""
        for block, error in report.failed.items():
            if block not in self._silent:
                self._silent.add(block)
                LOGGER.warning(
                    "%s: the %s registers did not answer: %s", self.name, block, error
                )

        for block in report.updated & self._silent:
            self._silent.discard(block)
            LOGGER.info("%s: the %s registers are answering again", self.name, block)


@dataclass(kw_only=True)
class SungrowModbusRuntimeData:
    """Runtime data for a SunGrow Modbus config entry."""

    readings: SungrowModbusDataUpdateCoordinator
    settings: SungrowModbusDataUpdateCoordinator
    device_info: DeviceInfo
    # The most the battery power controls go to, if the user set one.
    battery_max_power: int | None = None
    # What the force battery action drives, while it is enabled and added.
    operating_mode: SungrowModbusOperatingModeSelectEntity | None = None

    @property
    def inverter(self) -> SungrowInverter:
        """Return the polled inverter, which both coordinators share."""
        return self.readings.inverter

    def coordinator_for(
        self, blocks: tuple[Block, ...]
    ) -> SungrowModbusDataUpdateCoordinator:
        """Return the coordinator that refreshes an entity reading these blocks.

        A value that mixes measurements and settings moves with the
        measurements, so it follows the faster of the two.
        """
        if blocks and all(block in self.settings.blocks for block in blocks):
            return self.settings
        return self.readings

    def failed(self, block: Block) -> bool:
        """Return whether a block did not answer its coordinator's last poll."""
        return any(
            # Settings that never answered have no report at all.
            coordinator.data is not None and block.name in coordinator.data.failed
            for coordinator in (self.readings, self.settings)
        )
