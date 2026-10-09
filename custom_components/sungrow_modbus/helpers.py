"""Helpers for the SunGrow Modbus integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from homeassistant.const import CONF_HOST, CONF_PORT
from modbus_connection import ModbusTcpParams, ModbusUnit

from .const import CONF_CONNECTION, CONF_READINGS_INTERVAL, CONNECTION_WINET


@dataclass(frozen=True, kw_only=True)
class LinkTiming:
    """How patient to be with the device on the other end of the link."""

    message_spacing: float
    timeout: float
    connect_delay: float | None
    # How often the measurements are read, unless the options say otherwise,
    # and the least the options can set: a poll has to finish well within it.
    readings_interval: timedelta
    min_readings_interval: timedelta


# The WiNet-S relays every request over the inverter's internal bus. It needs a
# quiet gap between requests, takes a while to answer, and drops requests that
# come right after a connection opens. The values are the ones mkaiser's YAML
# package and its installation guide use for a WiNet-S.
# Polling it more often than every 10 seconds makes it drop more of them.
WINET_TIMING: Final = LinkTiming(
    message_spacing=0.03,
    timeout=30,
    connect_delay=15,
    readings_interval=timedelta(seconds=10),
    min_readings_interval=timedelta(seconds=5),
)

# The inverter's own LAN port answers like any Modbus TCP device. Every 5
# seconds matches the YAML package's fastest values, in a few block reads.
LAN_TIMING: Final = LinkTiming(
    message_spacing=0.005,
    timeout=10,
    connect_delay=None,
    readings_interval=timedelta(seconds=5),
    min_readings_interval=timedelta(seconds=2),
)


def link_timing(connection: str) -> LinkTiming:
    """Return how patient to be with the device behind a connection."""
    return WINET_TIMING if connection == CONNECTION_WINET else LAN_TIMING


def readings_interval(data: Mapping[str, Any], options: Mapping[str, Any]) -> timedelta:
    """Return how often to read the measurements.

    The one set in the options, if any, but never below what the connection
    allows: the connection may have changed since it was set.
    """
    timing = link_timing(data[CONF_CONNECTION])
    if (seconds := options.get(CONF_READINGS_INTERVAL)) is None:
        return timing.readings_interval
    return max(timedelta(seconds=seconds), timing.min_readings_interval)


def create_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def apply_link_timing(unit: ModbusUnit, connection: str) -> None:
    """Tell the shared link how patient the device behind it needs it to be."""
    timing = link_timing(connection)
    unit.set_message_spacing(timing.message_spacing)
    unit.require_timeout(timing.timeout)
    unit.require_connect_delay(timing.connect_delay)
