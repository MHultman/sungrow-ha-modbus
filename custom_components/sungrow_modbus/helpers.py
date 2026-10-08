"""Helpers for the SunGrow Modbus integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.const import CONF_HOST, CONF_PORT
from modbus_connection import ModbusTcpParams, ModbusUnit

from .const import CONNECTION_WINET


@dataclass(frozen=True, kw_only=True)
class LinkTiming:
    """How patient to be with the device on the other end of the link."""

    message_spacing: float
    timeout: float
    connect_delay: float | None


# The WiNet-S relays every request over the inverter's internal bus. It needs a
# quiet gap between requests, takes a while to answer, and drops requests that
# come right after a connection opens. The values are the ones mkaiser's YAML
# package and its installation guide use for a WiNet-S.
WINET_TIMING: Final = LinkTiming(message_spacing=0.03, timeout=30, connect_delay=15)

# The inverter's own LAN port answers like any Modbus TCP device.
LAN_TIMING: Final = LinkTiming(message_spacing=0.005, timeout=10, connect_delay=None)


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def apply_link_timing(unit: ModbusUnit, connection: str) -> None:
    """Tell the shared link how patient the device behind it needs it to be."""
    timing = WINET_TIMING if connection == CONNECTION_WINET else LAN_TIMING
    unit.set_message_spacing(timing.message_spacing)
    unit.require_timeout(timing.timeout)
    unit.require_connect_delay(timing.connect_delay)
