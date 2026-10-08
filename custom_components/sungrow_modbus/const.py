"""Constants for the SunGrow Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "sungrow_modbus"
LOGGER = logging.getLogger(__package__)

CONF_CONNECTION: Final = "connection"
CONF_UNIT_ID: Final = "unit_id"

# How the inverter is reached. The WiNet-S dongle relays Modbus TCP to the
# inverter over its internal bus and needs far more patience than the inverter's
# own LAN port.
CONNECTION_WINET: Final = "winet"
CONNECTION_LAN: Final = "lan"

# Sungrow's factory defaults on both the LAN port and the WiNet-S.
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

# Local Modbus is cheap to read and PV production moves fast.
SCAN_INTERVAL: Final = timedelta(seconds=10)

# Settings only move when something writes them, so they do not need a
# measurement's cadence. A write here refreshes them straight away.
SETTINGS_SCAN_INTERVAL: Final = timedelta(seconds=60)
