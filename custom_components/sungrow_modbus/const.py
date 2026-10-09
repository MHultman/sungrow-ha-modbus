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

# Settings only move when something writes them, so they do not need a
# measurement's cadence. A write here refreshes them straight away.
SETTINGS_SCAN_INTERVAL: Final = timedelta(seconds=60)

# An optional cap on the battery power controls, set in the options. mkaiser's
# guide recommends a conservative limit for the battery's health.
CONF_BATTERY_MAX_POWER: Final = "battery_max_power"

# An optional measurement interval, set in the options, in seconds. Left
# unset, the connection's default applies.
CONF_READINGS_INTERVAL: Final = "readings_interval"

# Whether entities go unavailable while the inverter does not answer, set in
# the options. By default they keep the last value read.
CONF_SHOW_UNAVAILABLE: Final = "show_unavailable"
MAX_READINGS_INTERVAL: Final = timedelta(minutes=5)

# Forces the battery to charge, discharge or idle for a while, then goes back
# to self-consumption. For energy managers and automations.
SERVICE_FORCE_BATTERY: Final = "force_battery"
ATTR_MODE: Final = "mode"
ATTR_POWER: Final = "power"
ATTR_DURATION: Final = "duration"
MAX_FORCE_DURATION: Final = timedelta(hours=24)
