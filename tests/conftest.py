"""Fixtures for the SunGrow Modbus tests.

The ``mock_modbus_connection`` fixture comes from the ``modbus-connection``
library's pytest plugin. Seeding the unit's input registers drives the
integration exactly as an inverter would.
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import PropertyMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusUnit
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sungrow_modbus.const import (
    CONF_CONNECTION,
    CONF_UNIT_ID,
    CONNECTION_WINET,
    DOMAIN,
)

HOST = "192.0.2.10"
PORT = 502
UNIT_ID = 1
# Synthetic: shaped like a real one, belonging to no inverter.
SERIAL_NUMBER = "A2101234567"
SH8_0RT_V112 = 0x0E0E


def entry_data(**overrides: Any) -> dict[str, Any]:
    """Config entry data for an inverter behind a WiNet-S."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_CONNECTION: CONNECTION_WINET,
        CONF_UNIT_ID: UNIT_ID,
        **overrides,
    }


def _string(text: str, words: int) -> list[int]:
    """Encode text the way Sungrow pads it: two characters a word, then NULs."""
    padded = text.encode().ljust(words * 2, b"\0")
    return [(padded[i] << 8) | padded[i + 1] for i in range(0, words * 2, 2)]


def _u32(value: int) -> list[int]:
    """Encode a 32-bit value low word first, as Sungrow does."""
    value &= 0xFFFFFFFF
    return [value & 0xFFFF, value >> 16]


def _i16(value: int) -> int:
    return value & 0xFFFF


def seed_inverter(
    unit: MockModbusUnit,
    device_type_code: int = SH8_0RT_V112,
    serial_number: str = SERIAL_NUMBER,
) -> None:
    """Seed a unit with a Sungrow hybrid on a sunny afternoon.

    The PV strings make about 3.4 kW, the battery charges at 1.2 kW, the house
    uses 1.5 kW and the rest goes to the grid. No smart meter is wired to the
    inverter, so the meter registers hold their "not available" markers.
    """
    unit.input.update(
        {
            4953: _string("ARM_SAPPHIRE-H_V11_V01_B", 15),
            4968: _string("MDSP_SAPPHIRE-H_V11_V01_B", 15),
            4989: _string(serial_number, 10),
            4999: device_type_code,
            5000: 80,  # rated output, 8000 W
            5002: 123,  # daily output, 12.3 kWh
            5003: _u32(456789),  # total output, 45678.9 kWh
            5007: 352,  # inverter temperature, 35.2 °C
            5010: [5148, 52, 2258, 31, 0xFFFF, 0xFFFF],  # MPPT 1-3 V/A
            5016: _u32(3377),  # total DC power
            5018: [2301, 2312, 2295],  # phase voltages
            5032: _u32(-150),  # reactive power
            5034: 998,  # power factor 0.998
            5213: _u32(-1200),  # battery power: charging at 1.2 kW
            5241: 5001,  # grid frequency, 50.01 Hz
            5600: _u32(0x7FFFFFFF) * 4,  # meter powers, not available
            5621: [0, 1000],  # export power limit range, 0-10000 W
            5627: 50,  # battery converter rating, 5000 W
            5630: _i16(-25),  # battery current, -2.5 A
            5634: [30, 30],  # BMS current limits
            5638: 960,  # battery capacity, 9.60 kWh
            5722: [100, 110, 120],  # backup phase powers
            5725: _u32(330),  # total backup power
            5740: [0x7FFF] * 3,  # meter voltages, not available
            5743: [0xFFFF] * 3,  # meter currents, not available
            12999: 0x0800,  # running state: forced mode
            13000: 0x1B,  # PV generating, battery charging, load, exporting
            13001: 254,  # daily PV generation, 25.4 kWh
            13002: _u32(512345),
            13004: 50,
            13005: _u32(123456),
            13007: _u32(1500),  # load power
            13009: _u32(677),  # export power
            13011: 31,
            13012: _u32(50000),
            13016: 80,
            13017: _u32(200000),
            13019: 4012,  # battery voltage, 401.2 V
            13022: 654,  # battery level, 65.4 %
            13023: 990,  # state of health, 99.0 %
            13024: 221,  # battery temperature, 22.1 °C
            13025: 40,  # daily battery discharge, 4.0 kWh
            13026: _u32(90000),
            13030: [48, 49, 50],  # phase currents
            13033: _u32(3300),  # total active power
            13035: 60,  # daily import, 6.0 kWh
            13036: _u32(252061),
            13039: 45,  # daily battery charge, 4.5 kWh
            13040: _u32(95000),
            13044: 70,  # daily export, 7.0 kWh
            13045: _u32(150000),
        }
    )


def seed_settings(unit: MockModbusUnit) -> None:
    """Seed a unit's settings: self-consumption, export limited to 8 kW.

    One address per register, so a write to one leaves its neighbours be.
    """
    settings: dict[int, int | list[int]] = {
        13001: 3,  # load adjustment mode: disabled
        13010: 0x55,  # load adjustment: off
        13049: [0, 0xCC, 4200],  # EMS mode, forced command, forced power
        13057: [1000, 50],  # max SoC 100.0 %, min SoC 5.0 %
        13073: [8000, 0x55],  # export power limit, backup mode off
        13086: 0xAA,  # export power limit: on
        13099: 5,  # reserved SoC for backup
        33046: [1060, 420],  # max charge 10600 W, max discharge 4200 W
        33148: [0, 19],  # charging start 0 W, discharging start 190 W
    }
    for address, value in settings.items():
        words = value if isinstance(value, list) else [value]
        unit.holding.update(
            {address + offset: word for offset, word in enumerate(words)}
        )


def set_u32(unit: MockModbusUnit, address: int, value: int) -> None:
    """Change a 32-bit register on a seeded unit."""
    unit.input[address] = _u32(value)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Create entities that are disabled by default as enabled."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


@pytest.fixture
def mock_modbus_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """Return a seeded Sungrow inverter on unit ``UNIT_ID``."""
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    seed_inverter(unit)
    seed_settings(unit)
    return unit


@pytest.fixture(autouse=True)
def mock_shared_connection(
    mock_modbus_connection: MockModbusConnection, mock_modbus_unit: MockModbusUnit
) -> Generator[None]:
    """Hand out units on the seeded mock instead of opening a real connection."""

    @asynccontextmanager
    async def async_temporary_unit(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> AsyncIterator[ModbusUnit]:
        yield mock_modbus_connection.for_unit(unit_id)

    with (
        patch(
            "custom_components.sungrow_modbus.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: (
                mock_modbus_connection.for_unit(unit_id)
            ),
        ),
        patch(
            "custom_components.sungrow_modbus.config_flow.async_get_temporary_unit",
            async_temporary_unit,
        ),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a SunGrow Modbus config entry for the seeded inverter."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sungrow SH8.0RT-V112",
        unique_id=SERIAL_NUMBER,
        data=entry_data(),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration for the seeded inverter."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
