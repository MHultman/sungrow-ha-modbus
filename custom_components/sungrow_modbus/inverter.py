"""Read a Sungrow hybrid inverter over a shared Modbus unit.

Nothing here knows about Home Assistant: it reads blocks of registers, keeps
the words they returned, and decodes values from them on request.
"""

from dataclasses import dataclass, field
from typing import Self

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
)

from .models import InverterModel, inverter_model
from .registers import (
    ARM_SOFTWARE,
    BACKUP_METER,
    BATTERY_GRID,
    DEVICE_TYPE_CODE,
    DSP_SOFTWARE,
    IDENTITY,
    INVERTER,
    METER_BMS,
    MPPT4,
    RATED_OUTPUT_POWER,
    SERIAL_NUMBER,
    SYSTEM,
    Block,
    Register,
)


class SungrowError(Exception):
    """The inverter did not give what was asked for."""


class SungrowConnectionError(SungrowError):
    """Nothing answered on the link."""


@dataclass(frozen=True, kw_only=True)
class PollReport:
    """Which blocks a poll refreshed, and why the others did not answer."""

    updated: frozenset[str]
    failed: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Identity:
    """Who the inverter is, as it reports itself."""

    serial_number: str
    device_type_code: int
    model: InverterModel
    arm_software: str | None
    dsp_software: str | None
    rated_output_power: int | None


async def _async_read(unit: ModbusUnit, block: Block) -> list[int]:
    """Read a block, translating a link that does not answer."""
    try:
        return await unit.read_input_registers(block.start, block.count)
    except (ModbusConnectionError, ModbusTimeoutError) as err:
        raise SungrowConnectionError(f"{block.name}: {err}") from err


class SungrowInverter:
    """A Sungrow hybrid inverter and the values it last reported."""

    def __init__(self, unit: ModbusUnit, identity: Identity) -> None:
        """Initialize the inverter for an identity it reported."""
        self._unit = unit
        self.identity = identity
        self._words: dict[str, list[int]] = {}

        blocks = [INVERTER, BATTERY_GRID, METER_BMS, BACKUP_METER, SYSTEM]
        if identity.model.mppt_count >= 4:
            blocks.append(MPPT4)
        self.blocks: tuple[Block, ...] = tuple(blocks)

    @classmethod
    async def async_probe(cls, unit: ModbusUnit) -> Self:
        """Ask the unit who it is.

        Raises `SungrowConnectionError` when nothing answers, and `SungrowError`
        when something does but it is no Sungrow hybrid inverter.
        """
        try:
            words = await _async_read(unit, IDENTITY)
        except ModbusError as err:
            raise SungrowError(f"identity: {err}") from err

        serial_number = SERIAL_NUMBER.decode(words)
        device_type_code = DEVICE_TYPE_CODE.decode(words)
        if not isinstance(serial_number, str) or not isinstance(device_type_code, int):
            raise SungrowError("identity: no serial number or device type code")

        identity = Identity(
            serial_number=serial_number,
            device_type_code=device_type_code,
            model=inverter_model(device_type_code),
            arm_software=_string(ARM_SOFTWARE.decode(words)),
            dsp_software=_string(DSP_SOFTWARE.decode(words)),
            rated_output_power=_integer(RATED_OUTPUT_POWER.decode(words)),
        )
        return cls(unit, identity)

    async def async_update(self) -> PollReport:
        """Read every block, keeping the words of those that answered.

        A block the inverter refuses fails on its own. A link that stops
        answering ends the poll, since every later block would wait out the
        same timeout.
        """
        updated: set[str] = set()
        failed: dict[str, str] = {}

        for block in self.blocks:
            try:
                self._words[block.name] = await _async_read(self._unit, block)
            except ModbusError as err:
                failed[block.name] = str(err)
            else:
                updated.add(block.name)

        return PollReport(updated=frozenset(updated), failed=failed)

    def value(self, register: Register) -> float | int | str | None:
        """Return a register's value as its block last reported it."""
        if (words := self._words.get(register.block.name)) is None:
            return None
        return register.decode(words)

    @property
    def raw(self) -> dict[str, list[int]]:
        """Return the words each block last returned."""
        return dict(self._words)


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None
