"""Read and write a Sungrow hybrid inverter over a shared Modbus unit.

Nothing here knows about Home Assistant: it reads blocks of registers, keeps
the words they returned, decodes values from them on request, and writes
settings.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
)

from .models import Family, InverterModel, inverter_model
from .registers import (
    ARM_SOFTWARE,
    BACKUP_METER,
    BACKUP_RESERVE,
    BATTERY_GRID,
    BATTERY_POWER_LIMITS,
    BATTERY_START_POWER,
    DEVICE_TYPE_CODE,
    DSP_SOFTWARE,
    EMS,
    EXPORT_LIMIT_BACKUP,
    EXPORT_LIMIT_SWITCH,
    IDENTITY,
    INVERTER,
    LOAD_ADJUSTMENT_MODE,
    LOAD_ADJUSTMENT_SWITCH,
    METER_BMS,
    MPPT4,
    RATED_OUTPUT_POWER,
    SERIAL_NUMBER,
    SOC_LIMITS,
    SYSTEM,
    Block,
    Register,
    Space,
)


class SungrowError(Exception):
    """The inverter did not give what was asked for."""


class SungrowConnectionError(SungrowError):
    """Nothing answered on the link."""


class SungrowRejectedError(SungrowError):
    """The inverter refused a value written to it."""


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
    read = (
        unit.read_holding_registers
        if block.space is Space.HOLDING
        else unit.read_input_registers
    )
    try:
        return await read(block.start, block.count)
    except (ModbusConnectionError, ModbusTimeoutError) as err:
        raise SungrowConnectionError(f"{block.name}: {err}") from err


def _reading_blocks(model: InverterModel) -> tuple[Block, ...]:
    """Return the measurement blocks a model serves."""
    blocks = [INVERTER, BATTERY_GRID, METER_BMS, BACKUP_METER, SYSTEM]
    if model.mppt_count >= 4:
        blocks.append(MPPT4)
    return tuple(blocks)


def _setting_blocks(model: InverterModel) -> tuple[Block, ...]:
    """Return the settings blocks a model serves.

    None for a model this integration does not know, which gets no controls.
    The charge and discharge start powers are not documented by Sungrow and
    have only been seen working on the RT models.
    """
    if not model.known:
        return ()
    blocks = [
        EMS,
        SOC_LIMITS,
        BACKUP_RESERVE,
        EXPORT_LIMIT_BACKUP,
        EXPORT_LIMIT_SWITCH,
        BATTERY_POWER_LIMITS,
        LOAD_ADJUSTMENT_MODE,
        LOAD_ADJUSTMENT_SWITCH,
    ]
    if model.family is Family.RT:
        blocks.append(BATTERY_START_POWER)
    return tuple(blocks)


class SungrowInverter:
    """A Sungrow hybrid inverter and the values it last reported."""

    def __init__(self, unit: ModbusUnit, identity: Identity) -> None:
        """Initialize the inverter for an identity it reported."""
        self._unit = unit
        self.identity = identity
        self._words: dict[str, list[int]] = {}
        # Measurements move by the second; settings only when written.
        self.reading_blocks = _reading_blocks(identity.model)
        self.setting_blocks = _setting_blocks(identity.model)

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

    async def async_update(self, blocks: Iterable[Block]) -> PollReport:
        """Read blocks, keeping the words of those that answered.

        A block the inverter refuses fails on its own. A link that stops
        answering ends the poll, since every later block would wait out the
        same timeout.
        """
        updated: set[str] = set()
        failed: dict[str, str] = {}

        for block in blocks:
            try:
                self._words[block.name] = await _async_read(self._unit, block)
            except ModbusError as err:
                failed[block.name] = str(err)
            else:
                updated.add(block.name)

        return PollReport(updated=frozenset(updated), failed=failed)

    async def async_write(self, register: Register, value: float) -> None:
        """Write a setting, and keep it as what its block last reported.

        Raises `ValueError` for a value the register cannot hold,
        `SungrowConnectionError` when nothing answers, and
        `SungrowRejectedError` when the inverter refuses the value.
        """
        raw = register.encode(value)
        try:
            await self._unit.write_register(register.address, raw)
        except (ModbusConnectionError, ModbusTimeoutError) as err:
            raise SungrowConnectionError(f"{register.address}: {err}") from err
        except ModbusError as err:
            raise SungrowRejectedError(f"{register.address}: {err}") from err

        if (words := self._words.get(register.block.name)) is not None:
            words[register.address - register.block.start] = raw

    async def async_set(self, register: Register, value: float) -> None:
        """Write a setting, unless the inverter already holds it.

        Energy managers send the same setting again and again, and every
        write is stored by the inverter. A setting that looks unchanged costs
        a read instead: the cached words can be a minute old, and a change
        made in iSolarCloud since must not make a write go missing. If that
        read fails, the setting is written anyway.

        Raises as `async_write` does.
        """
        raw = register.encode(value)
        if self._raw(register) == raw and await self._async_still_holds(register, raw):
            return
        await self.async_write(register, value)

    def _raw(self, register: Register) -> int | None:
        if (words := self._words.get(register.block.name)) is None:
            return None
        return words[register.address - register.block.start]

    async def _async_still_holds(self, register: Register, raw: int) -> bool:
        try:
            self._words[register.block.name] = await _async_read(
                self._unit, register.block
            )
        except (ModbusError, SungrowConnectionError):
            return False
        return self._raw(register) == raw

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
