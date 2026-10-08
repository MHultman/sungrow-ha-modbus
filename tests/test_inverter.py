"""Tests for reading a Sungrow inverter, outside of Home Assistant."""

from modbus_connection import (
    IllegalDataAddressError,
    IllegalDataValueError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest

from custom_components.sungrow_modbus.inverter import (
    SungrowConnectionError,
    SungrowError,
    SungrowInverter,
    SungrowRejectedError,
)
from custom_components.sungrow_modbus.models import inverter_model
from custom_components.sungrow_modbus.registers import (
    BATTERY_POWER,
    INVERTER,
    METER_ACTIVE_POWER,
    MIN_SOC,
    MPPT4,
    PHASE_A_VOLTAGE,
    REACTIVE_POWER,
    SYSTEM,
    Block,
    Kind,
    Register,
    Space,
)

from .conftest import SERIAL_NUMBER, seed_inverter

TEST_BLOCK = Block(name="test", start=100, count=4)


@pytest.mark.parametrize(
    ("register", "words", "expected"),
    [
        (Register(block=TEST_BLOCK, address=100, kind=Kind.UINT16), [65535], 65535),
        (Register(block=TEST_BLOCK, address=100, kind=Kind.INT16), [65535], -1),
        # Low word first: 0x0001_0002.
        (Register(block=TEST_BLOCK, address=100, kind=Kind.UINT32), [2, 1], 65538),
        (
            Register(block=TEST_BLOCK, address=100, kind=Kind.INT32),
            [0xFFFE, 0xFFFF],
            -2,
        ),
        (
            Register(block=TEST_BLOCK, address=100, kind=Kind.UINT16, scale=0.1),
            [2301],
            230.1,
        ),
        (
            Register(block=TEST_BLOCK, address=100, kind=Kind.INT16, scale=0.001),
            [998],
            0.998,
        ),
        (
            Register(block=TEST_BLOCK, address=100, kind=Kind.UINT16, scale=100),
            [80],
            8000,
        ),
        (
            Register(block=TEST_BLOCK, address=101, kind=Kind.UINT16),
            [0, 7, 0, 0],
            7,
        ),
    ],
)
def test_register_decode(register: Register, words: list[int], expected: float) -> None:
    """Test numbers decode with their sign, word order and scale."""
    assert register.decode(words) == expected


def test_register_invalid_marker() -> None:
    """Test the "not available" marker decodes to no value."""
    register = Register(
        block=TEST_BLOCK, address=100, kind=Kind.INT32, invalid=0x7FFFFFFF
    )

    assert register.decode([0xFFFF, 0x7FFF]) is None


def test_register_string() -> None:
    """Test a NUL-padded string decodes without its padding, and empty to None."""
    register = Register(block=TEST_BLOCK, address=100, kind=Kind.STRING, length=2)

    assert register.decode([0x4142, 0x4300]) == "ABC"
    assert register.decode([0, 0]) is None


def test_register_outside_block() -> None:
    """Test a register that does not fit its block is refused."""
    with pytest.raises(ValueError, match="outside test"):
        Register(block=TEST_BLOCK, address=103, kind=Kind.UINT32)


def test_unknown_model() -> None:
    """Test a device type code nobody knows is read, but marked unknown."""
    model = inverter_model(0x0EFF)

    assert model.name == "Unknown (0x0EFF)"
    assert not model.known
    assert model.mppt_count == 2
    assert model.three_phase


async def test_unknown_model_reads_no_settings(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test settings are never read from a model nobody knows."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0EFF)

    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert inverter.setting_blocks == ()


async def test_probe(mock_modbus_unit: MockModbusUnit) -> None:
    """Test the probe reads who the inverter is."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert inverter.identity.serial_number == SERIAL_NUMBER
    assert inverter.identity.model.name == "SH8.0RT-V112"
    assert inverter.identity.arm_software == "ARM_SAPPHIRE-H_V11_V01_B"
    assert inverter.identity.dsp_software == "MDSP_SAPPHIRE-H_V11_V01_B"
    assert inverter.identity.rated_output_power == 8000
    assert MPPT4 not in inverter.reading_blocks


async def test_probe_four_mppts(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a model with a fourth MPPT gets that block polled too."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0D1B)  # SH10RS

    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert MPPT4 in inverter.reading_blocks


async def test_probe_no_answer(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a link nobody answers on is a connection error."""
    mock_modbus_unit.fail_requests(ModbusConnectionError("refused"))

    with pytest.raises(SungrowConnectionError):
        await SungrowInverter.async_probe(mock_modbus_unit)


async def test_probe_not_sungrow(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a device refusing the identity registers is not a Sungrow."""
    mock_modbus_unit.fail_read(4989, IllegalDataAddressError(), register_type="input")

    with pytest.raises(SungrowError):
        await SungrowInverter.async_probe(mock_modbus_unit)


async def test_probe_no_serial_number(mock_modbus_unit: MockModbusUnit) -> None:
    """Test identity registers holding nothing are not a Sungrow either."""
    mock_modbus_unit.input[4989] = [0] * 10

    with pytest.raises(SungrowError, match="no serial number"):
        await SungrowInverter.async_probe(mock_modbus_unit)


async def test_update(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a poll reads every block and decodes from what came back."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    report = await inverter.async_update(inverter.reading_blocks)

    assert report.updated == {block.name for block in inverter.reading_blocks}
    assert report.failed == {}
    assert inverter.value(PHASE_A_VOLTAGE) == 230.1
    assert inverter.value(REACTIVE_POWER) == -150
    assert inverter.value(BATTERY_POWER) == -1200
    assert inverter.value(METER_ACTIVE_POWER) is None


async def test_update_block_refused(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a block the inverter refuses fails alone, keeping its last words."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.reading_blocks)

    mock_modbus_unit.fail_read(
        INVERTER.start, IllegalDataAddressError(), register_type="input"
    )
    report = await inverter.async_update(inverter.reading_blocks)

    assert INVERTER.name in report.failed
    assert SYSTEM.name in report.updated
    assert inverter.value(PHASE_A_VOLTAGE) == 230.1


async def test_update_link_down(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a link that stops answering ends the poll at the first block."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    mock_modbus_unit.read_events.clear()
    mock_modbus_unit.fail_requests(ModbusConnectionError("gone"))

    with pytest.raises(SungrowConnectionError):
        await inverter.async_update(inverter.reading_blocks)

    assert len(mock_modbus_unit.read_events) == 1


async def test_value_before_first_poll(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a block never read has no values."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert inverter.value(PHASE_A_VOLTAGE) is None


HOLDING_BLOCK = Block(name="settings", space=Space.HOLDING, start=200, count=2)


@pytest.mark.parametrize(
    ("scale", "value", "raw"),
    [(1, 4200, 4200), (0.1, 15, 150), (0.1, 15.04, 150), (10, 10600, 1060)],
)
def test_register_encode(scale: float, value: float, raw: int) -> None:
    """Test a value is written in the register's own units."""
    register = Register(block=HOLDING_BLOCK, address=200, kind=Kind.UINT16, scale=scale)

    assert register.encode(value) == raw


@pytest.mark.parametrize(
    "register",
    [
        # Measurements are input registers, which cannot be written.
        Register(block=TEST_BLOCK, address=100, kind=Kind.UINT16),
        Register(block=HOLDING_BLOCK, address=200, kind=Kind.INT32),
    ],
)
def test_register_not_writable(register: Register) -> None:
    """Test only single unsigned settings words are ever written."""
    with pytest.raises(ValueError, match="not writable"):
        register.encode(1)


@pytest.mark.parametrize("value", [-1, 0x10000, 0xFFFF])
def test_register_encode_out_of_range(value: int) -> None:
    """Test a value the word cannot hold, or its "not available" marker, is refused."""
    register = Register(
        block=HOLDING_BLOCK, address=200, kind=Kind.UINT16, invalid=0xFFFF
    )

    with pytest.raises(ValueError, match="does not fit"):
        register.encode(value)


async def test_write(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a write reaches the inverter and is kept as its block's value."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)

    await inverter.async_write(MIN_SOC, 15)

    assert mock_modbus_unit.holding[13058] == 150
    assert inverter.value(MIN_SOC) == 15


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (IllegalDataValueError(), SungrowRejectedError),
        (ModbusConnectionError("gone"), SungrowConnectionError),
    ],
)
async def test_write_fails(
    mock_modbus_unit: MockModbusUnit, error: Exception, raised: type[Exception]
) -> None:
    """Test a refused write and a lost one are told apart."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)
    mock_modbus_unit.fail_write(13058, error)

    with pytest.raises(raised):
        await inverter.async_write(MIN_SOC, 15)

    assert inverter.value(MIN_SOC) == 5


async def test_set_skips_a_setting_already_held(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a setting the inverter holds costs a read, not a write."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    reads_before = len(mock_modbus_unit.read_events)

    await inverter.async_set(MIN_SOC, 5)

    assert writes == []
    assert [read.address for read in mock_modbus_unit.read_events[reads_before:]] == [
        13057
    ]


async def test_set_writes_a_change(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a changed setting is written straight away, without a read."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)
    reads_before = len(mock_modbus_unit.read_events)

    await inverter.async_set(MIN_SOC, 15)

    assert mock_modbus_unit.holding[13058] == 150
    assert len(mock_modbus_unit.read_events) == reads_before


async def test_set_writes_a_setting_changed_elsewhere(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test an out-of-date cached value cannot make a write go missing."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)
    mock_modbus_unit.holding[13058] = 200  # changed in iSolarCloud

    await inverter.async_set(MIN_SOC, 5)

    assert mock_modbus_unit.holding[13058] == 50


async def test_set_writes_when_the_check_fails(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test a setting that could not be checked is written anyway."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update(inverter.setting_blocks)
    mock_modbus_unit.fail_read(13057, ModbusTimeoutError("no answer"))
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)

    await inverter.async_set(MIN_SOC, 5)

    assert [(write.address, write.values) for write in writes] == [(13058, [50])]
