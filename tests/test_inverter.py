"""Tests for reading a Sungrow inverter, outside of Home Assistant."""

from modbus_connection import IllegalDataAddressError, ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest

from custom_components.sungrow_modbus.inverter import (
    SungrowConnectionError,
    SungrowError,
    SungrowInverter,
)
from custom_components.sungrow_modbus.models import inverter_model
from custom_components.sungrow_modbus.registers import (
    BATTERY_POWER,
    INVERTER,
    METER_ACTIVE_POWER,
    MPPT4,
    PHASE_A_VOLTAGE,
    REACTIVE_POWER,
    SYSTEM,
    Block,
    Kind,
    Register,
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
    """Test a device type code nobody knows still gets a usable model."""
    model = inverter_model(0x0EFF)

    assert model.name == "SH (0x0EFF)"
    assert model.mppt_count == 2
    assert model.three_phase


async def test_probe(mock_modbus_unit: MockModbusUnit) -> None:
    """Test the probe reads who the inverter is."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert inverter.identity.serial_number == SERIAL_NUMBER
    assert inverter.identity.model.name == "SH8.0RT-V112"
    assert inverter.identity.arm_software == "ARM_SAPPHIRE-H_V11_V01_B"
    assert inverter.identity.dsp_software == "MDSP_SAPPHIRE-H_V11_V01_B"
    assert inverter.identity.rated_output_power == 8000
    assert MPPT4 not in inverter.blocks


async def test_probe_four_mppts(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a model with a fourth MPPT gets that block polled too."""
    seed_inverter(mock_modbus_unit, device_type_code=0x0D1B)  # SH10RS

    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert MPPT4 in inverter.blocks


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

    report = await inverter.async_update()

    assert report.updated == {block.name for block in inverter.blocks}
    assert report.failed == {}
    assert inverter.value(PHASE_A_VOLTAGE) == 230.1
    assert inverter.value(REACTIVE_POWER) == -150
    assert inverter.value(BATTERY_POWER) == -1200
    assert inverter.value(METER_ACTIVE_POWER) is None


async def test_update_block_refused(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a block the inverter refuses fails alone, keeping its last words."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    await inverter.async_update()

    mock_modbus_unit.fail_read(
        INVERTER.start, IllegalDataAddressError(), register_type="input"
    )
    report = await inverter.async_update()

    assert INVERTER.name in report.failed
    assert SYSTEM.name in report.updated
    assert inverter.value(PHASE_A_VOLTAGE) == 230.1


async def test_update_link_down(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a link that stops answering ends the poll at the first block."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)
    mock_modbus_unit.read_events.clear()
    mock_modbus_unit.fail_requests(ModbusConnectionError("gone"))

    with pytest.raises(SungrowConnectionError):
        await inverter.async_update()

    assert len(mock_modbus_unit.read_events) == 1


async def test_value_before_first_poll(mock_modbus_unit: MockModbusUnit) -> None:
    """Test a block never read has no values."""
    inverter = await SungrowInverter.async_probe(mock_modbus_unit)

    assert inverter.value(PHASE_A_VOLTAGE) is None
