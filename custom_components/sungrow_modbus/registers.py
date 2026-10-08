"""The Modbus register map of Sungrow SH hybrid inverters.

Addresses are protocol addresses, one below the register numbers Sungrow's
documentation lists (its register 5003 is address 5002 here). Measurements are
input registers; settings are holding registers, which can also be written.
32-bit values put their low word first.

Registers are read in blocks rather than one by one: the WiNet-S answers a
request in about the same time whatever its size, and a block that refuses to
answer only takes its own values down with it. Each block spans registers the
inverter documents, so none of them should run into an address it rejects.

The register map follows mkaiser's Sungrow-SHx-Inverter-Modbus-Home-Assistant
package (MIT licensed, see NOTICE).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from math import floor, log10

from modbus_connection.decode import combine_words, decode_string


class Space(StrEnum):
    """The address space a block lives in."""

    INPUT = "input"
    HOLDING = "holding"


@dataclass(frozen=True, kw_only=True)
class Block:
    """A run of registers read in one request."""

    name: str
    start: int
    count: int
    space: Space = Space.INPUT


class Kind(Enum):
    """How a register's words encode its value."""

    UINT16 = auto()
    INT16 = auto()
    UINT32 = auto()
    INT32 = auto()
    STRING = auto()


_WORDS = {Kind.UINT16: 1, Kind.INT16: 1, Kind.UINT32: 2, Kind.INT32: 2}
_SIGNED_BITS = {Kind.INT16: 16, Kind.INT32: 32}


@dataclass(frozen=True, kw_only=True)
class Register:
    """One value inside a block."""

    block: Block
    address: int
    kind: Kind
    scale: float = 1
    # A string's length in words; numbers know their own.
    length: int = 0
    # The raw value the inverter reports for "not available", like 0x7FFFFFFF
    # for a meter power when no meter is wired to the inverter.
    invalid: int | None = None

    def __post_init__(self) -> None:
        """Check the register fits in its block."""
        end = self.address + self.words
        if self.address < self.block.start or end > self.block.start + self.block.count:
            raise ValueError(f"register {self.address} lies outside {self.block.name}")

    @property
    def words(self) -> int:
        """Return how many words the value takes."""
        return self.length if self.kind is Kind.STRING else _WORDS[self.kind]

    def decode(self, block_words: Sequence[int]) -> float | int | str | None:
        """Decode the value from the words its block returned."""
        offset = self.address - self.block.start
        words = list(block_words[offset : offset + self.words])

        if self.kind is Kind.STRING:
            return decode_string(words).strip() or None

        raw = combine_words(words, word_order="little")
        if raw == self.invalid:
            return None

        if (bits := _SIGNED_BITS.get(self.kind)) and raw >= 1 << (bits - 1):
            raw -= 1 << bits

        decimals = max(0, -floor(log10(self.scale)))
        if decimals == 0:
            return round(raw * self.scale)
        return round(raw * self.scale, decimals)

    def encode(self, value: float) -> int:
        """Encode a value into the word to write.

        Only single unsigned words are ever written. Raises `ValueError` for a
        value the register cannot hold.
        """
        if self.kind is not Kind.UINT16 or self.block.space is not Space.HOLDING:
            raise ValueError(f"register {self.address} is not writable")

        raw = round(value / self.scale)
        if not 0 <= raw <= 0xFFFF or raw == self.invalid:
            raise ValueError(f"{value} does not fit register {self.address}")
        return raw


# Who the inverter is. Read once while setting up.
IDENTITY = Block(name="identity", start=4953, count=48)
# PV strings, AC side and the inverter's own counters.
INVERTER = Block(name="inverter", start=5002, count=34)
# The fourth MPPT, only on the models that have one.
MPPT4 = Block(name="mppt4", start=5114, count=2)
BATTERY_GRID = Block(name="battery_grid", start=5213, count=29)
METER_BMS = Block(name="meter_bms", start=5600, count=39)
BACKUP_METER = Block(name="backup_meter", start=5722, count=24)
# The energy management system's view: power flows and energy counters.
SYSTEM = Block(name="system", start=12999, count=48)

ARM_SOFTWARE = Register(block=IDENTITY, address=4953, kind=Kind.STRING, length=15)
DSP_SOFTWARE = Register(block=IDENTITY, address=4968, kind=Kind.STRING, length=15)
SERIAL_NUMBER = Register(block=IDENTITY, address=4989, kind=Kind.STRING, length=10)
DEVICE_TYPE_CODE = Register(block=IDENTITY, address=4999, kind=Kind.UINT16)
RATED_OUTPUT_POWER = Register(block=IDENTITY, address=5000, kind=Kind.UINT16, scale=100)

# Energy counters, here and in the system block, mark their "not available"
# value: it would otherwise read as thousands of kWh, which long-term
# statistics would count as real energy.
DAILY_OUTPUT_ENERGY = Register(
    block=INVERTER, address=5002, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_OUTPUT_ENERGY = Register(
    block=INVERTER, address=5003, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
INVERTER_TEMPERATURE = Register(
    block=INVERTER, address=5007, kind=Kind.INT16, scale=0.1
)
MPPT1_VOLTAGE = Register(block=INVERTER, address=5010, kind=Kind.UINT16, scale=0.1)
MPPT1_CURRENT = Register(block=INVERTER, address=5011, kind=Kind.UINT16, scale=0.1)
MPPT2_VOLTAGE = Register(block=INVERTER, address=5012, kind=Kind.UINT16, scale=0.1)
MPPT2_CURRENT = Register(block=INVERTER, address=5013, kind=Kind.UINT16, scale=0.1)
MPPT3_VOLTAGE = Register(
    block=INVERTER, address=5014, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
MPPT3_CURRENT = Register(
    block=INVERTER, address=5015, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_DC_POWER = Register(block=INVERTER, address=5016, kind=Kind.UINT32)
PHASE_A_VOLTAGE = Register(block=INVERTER, address=5018, kind=Kind.UINT16, scale=0.1)
PHASE_B_VOLTAGE = Register(block=INVERTER, address=5019, kind=Kind.UINT16, scale=0.1)
PHASE_C_VOLTAGE = Register(block=INVERTER, address=5020, kind=Kind.UINT16, scale=0.1)
REACTIVE_POWER = Register(block=INVERTER, address=5032, kind=Kind.INT32)
POWER_FACTOR = Register(block=INVERTER, address=5034, kind=Kind.INT16, scale=0.001)

MPPT4_VOLTAGE = Register(
    block=MPPT4, address=5114, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
MPPT4_CURRENT = Register(
    block=MPPT4, address=5115, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)

# Positive while the battery discharges, negative while it charges.
BATTERY_POWER = Register(block=BATTERY_GRID, address=5213, kind=Kind.INT32)
GRID_FREQUENCY = Register(
    block=BATTERY_GRID, address=5241, kind=Kind.UINT16, scale=0.01
)

# Only valid with the smart meter wired directly to the inverter. Positive
# while importing from the grid.
METER_ACTIVE_POWER = Register(
    block=METER_BMS, address=5600, kind=Kind.INT32, invalid=0x7FFFFFFF
)
METER_PHASE_A_ACTIVE_POWER = Register(
    block=METER_BMS, address=5602, kind=Kind.INT32, invalid=0x7FFFFFFF
)
METER_PHASE_B_ACTIVE_POWER = Register(
    block=METER_BMS, address=5604, kind=Kind.INT32, invalid=0x7FFFFFFF
)
METER_PHASE_C_ACTIVE_POWER = Register(
    block=METER_BMS, address=5606, kind=Kind.INT32, invalid=0x7FFFFFFF
)
EXPORT_POWER_LIMIT_MIN = Register(
    block=METER_BMS, address=5621, kind=Kind.UINT16, scale=10, invalid=0xFFFF
)
EXPORT_POWER_LIMIT_MAX = Register(
    block=METER_BMS, address=5622, kind=Kind.UINT16, scale=10, invalid=0xFFFF
)
BDC_RATED_POWER = Register(block=METER_BMS, address=5627, kind=Kind.UINT16, scale=100)
BATTERY_CURRENT = Register(block=METER_BMS, address=5630, kind=Kind.INT16, scale=0.1)
BMS_MAX_CHARGING_CURRENT = Register(block=METER_BMS, address=5634, kind=Kind.UINT16)
BMS_MAX_DISCHARGING_CURRENT = Register(block=METER_BMS, address=5635, kind=Kind.UINT16)
BATTERY_CAPACITY = Register(block=METER_BMS, address=5638, kind=Kind.UINT16, scale=0.01)

BACKUP_PHASE_A_POWER = Register(block=BACKUP_METER, address=5722, kind=Kind.INT16)
BACKUP_PHASE_B_POWER = Register(block=BACKUP_METER, address=5723, kind=Kind.INT16)
BACKUP_PHASE_C_POWER = Register(block=BACKUP_METER, address=5724, kind=Kind.INT16)
TOTAL_BACKUP_POWER = Register(block=BACKUP_METER, address=5725, kind=Kind.INT32)
METER_PHASE_A_VOLTAGE = Register(
    block=BACKUP_METER, address=5740, kind=Kind.INT16, scale=0.1, invalid=0x7FFF
)
METER_PHASE_B_VOLTAGE = Register(
    block=BACKUP_METER, address=5741, kind=Kind.INT16, scale=0.1, invalid=0x7FFF
)
METER_PHASE_C_VOLTAGE = Register(
    block=BACKUP_METER, address=5742, kind=Kind.INT16, scale=0.1, invalid=0x7FFF
)
METER_PHASE_A_CURRENT = Register(
    block=BACKUP_METER, address=5743, kind=Kind.UINT16, scale=0.01, invalid=0xFFFF
)
METER_PHASE_B_CURRENT = Register(
    block=BACKUP_METER, address=5744, kind=Kind.UINT16, scale=0.01, invalid=0xFFFF
)
METER_PHASE_C_CURRENT = Register(
    block=BACKUP_METER, address=5745, kind=Kind.UINT16, scale=0.01, invalid=0xFFFF
)

RUNNING_STATE = Register(block=SYSTEM, address=12999, kind=Kind.UINT16)
# A bit field: PV generating, battery charging, and so on.
POWER_FLOW_STATUS = Register(block=SYSTEM, address=13000, kind=Kind.UINT16)
DAILY_PV_GENERATION = Register(
    block=SYSTEM, address=13001, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_PV_GENERATION = Register(
    block=SYSTEM, address=13002, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
DAILY_PV_EXPORT = Register(
    block=SYSTEM, address=13004, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_PV_EXPORT = Register(
    block=SYSTEM, address=13005, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
LOAD_POWER = Register(block=SYSTEM, address=13007, kind=Kind.INT32, invalid=0x7FFFFFFF)
# Positive while exporting to the grid, negative while importing.
EXPORT_POWER = Register(
    block=SYSTEM, address=13009, kind=Kind.INT32, invalid=0x7FFFFFFF
)
DAILY_BATTERY_CHARGE_FROM_PV = Register(
    block=SYSTEM, address=13011, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_BATTERY_CHARGE_FROM_PV = Register(
    block=SYSTEM, address=13012, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
DAILY_DIRECT_CONSUMPTION = Register(
    block=SYSTEM, address=13016, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_DIRECT_CONSUMPTION = Register(
    block=SYSTEM, address=13017, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
BATTERY_VOLTAGE = Register(block=SYSTEM, address=13019, kind=Kind.UINT16, scale=0.1)
BATTERY_LEVEL = Register(block=SYSTEM, address=13022, kind=Kind.UINT16, scale=0.1)
BATTERY_STATE_OF_HEALTH = Register(
    block=SYSTEM, address=13023, kind=Kind.UINT16, scale=0.1
)
BATTERY_TEMPERATURE = Register(block=SYSTEM, address=13024, kind=Kind.INT16, scale=0.1)
DAILY_BATTERY_DISCHARGE = Register(
    block=SYSTEM, address=13025, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_BATTERY_DISCHARGE = Register(
    block=SYSTEM, address=13026, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
PHASE_A_CURRENT = Register(block=SYSTEM, address=13030, kind=Kind.INT16, scale=0.1)
PHASE_B_CURRENT = Register(block=SYSTEM, address=13031, kind=Kind.INT16, scale=0.1)
PHASE_C_CURRENT = Register(block=SYSTEM, address=13032, kind=Kind.INT16, scale=0.1)
TOTAL_ACTIVE_POWER = Register(block=SYSTEM, address=13033, kind=Kind.INT32)
DAILY_IMPORT = Register(
    block=SYSTEM, address=13035, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_IMPORT = Register(
    block=SYSTEM, address=13036, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
DAILY_BATTERY_CHARGE = Register(
    block=SYSTEM, address=13039, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_BATTERY_CHARGE = Register(
    block=SYSTEM, address=13040, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)
DAILY_EXPORT = Register(
    block=SYSTEM, address=13044, kind=Kind.UINT16, scale=0.1, invalid=0xFFFF
)
TOTAL_EXPORT = Register(
    block=SYSTEM, address=13045, kind=Kind.UINT32, scale=0.1, invalid=0xFFFFFFFF
)

# Settings. Each block covers only registers Sungrow documents (or the
# community has reverse engineered), with no gaps, since an undocumented
# holding register may be refused and would take the block down with it.

# Writing 0xCF here starts the inverter, 0xCE stops it. Never read.
START_STOP = Block(name="start_stop", space=Space.HOLDING, start=12999, count=1)
LOAD_ADJUSTMENT_MODE = Block(
    name="load_adjustment_mode", space=Space.HOLDING, start=13001, count=1
)
LOAD_ADJUSTMENT_SWITCH = Block(
    name="load_adjustment_switch", space=Space.HOLDING, start=13010, count=1
)
EMS = Block(name="ems", space=Space.HOLDING, start=13049, count=3)
SOC_LIMITS = Block(name="soc_limits", space=Space.HOLDING, start=13057, count=2)
EXPORT_LIMIT_BACKUP = Block(
    name="export_limit_backup", space=Space.HOLDING, start=13073, count=2
)
EXPORT_LIMIT_SWITCH = Block(
    name="export_limit_switch", space=Space.HOLDING, start=13086, count=1
)
BACKUP_RESERVE = Block(name="backup_reserve", space=Space.HOLDING, start=13099, count=1)
BATTERY_POWER_LIMITS = Block(
    name="battery_power_limits", space=Space.HOLDING, start=33046, count=2
)
# Not documented by Sungrow, and only seen working on the SH-RT models.
BATTERY_START_POWER = Block(
    name="battery_start_power", space=Space.HOLDING, start=33148, count=2
)

# What a switch register holds while on and while off.
SWITCH_ON = 0xAA
SWITCH_OFF = 0x55

START_STOP_COMMAND = Register(block=START_STOP, address=12999, kind=Kind.UINT16)
LOAD_ADJUSTMENT_MODE_SELECTION = Register(
    block=LOAD_ADJUSTMENT_MODE, address=13001, kind=Kind.UINT16
)
LOAD_ADJUSTMENT_ENABLED = Register(
    block=LOAD_ADJUSTMENT_SWITCH, address=13010, kind=Kind.UINT16
)
EMS_MODE = Register(block=EMS, address=13049, kind=Kind.UINT16)
FORCED_CHARGE_DISCHARGE_COMMAND = Register(block=EMS, address=13050, kind=Kind.UINT16)
# Watts on the models it has been checked on, though Sungrow's documentation
# gives percent for the RT models.
FORCED_CHARGE_DISCHARGE_POWER = Register(block=EMS, address=13051, kind=Kind.UINT16)
MAX_SOC = Register(block=SOC_LIMITS, address=13057, kind=Kind.UINT16, scale=0.1)
MIN_SOC = Register(block=SOC_LIMITS, address=13058, kind=Kind.UINT16, scale=0.1)
EXPORT_POWER_LIMIT = Register(
    block=EXPORT_LIMIT_BACKUP, address=13073, kind=Kind.UINT16
)
BACKUP_MODE = Register(block=EXPORT_LIMIT_BACKUP, address=13074, kind=Kind.UINT16)
EXPORT_POWER_LIMIT_ENABLED = Register(
    block=EXPORT_LIMIT_SWITCH, address=13086, kind=Kind.UINT16
)
BACKUP_RESERVE_SOC = Register(block=BACKUP_RESERVE, address=13099, kind=Kind.UINT16)
BATTERY_MAX_CHARGE_POWER = Register(
    block=BATTERY_POWER_LIMITS, address=33046, kind=Kind.UINT16, scale=10
)
BATTERY_MAX_DISCHARGE_POWER = Register(
    block=BATTERY_POWER_LIMITS, address=33047, kind=Kind.UINT16, scale=10
)
BATTERY_CHARGING_START_POWER = Register(
    block=BATTERY_START_POWER, address=33148, kind=Kind.UINT16, scale=10, invalid=0xFFFF
)
BATTERY_DISCHARGING_START_POWER = Register(
    block=BATTERY_START_POWER, address=33149, kind=Kind.UINT16, scale=10, invalid=0xFFFF
)
