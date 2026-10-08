# Changelog

## 0.2.0 - 2026-10-08

The first release. Not yet tested on real hardware: so far it has only run against a simulated SH8.0RT-V112. Check each control on your own system before you automate it.

Needs Home Assistant 2026.10 or newer. Remove the `modbus:` part of mkaiser's `modbus_sungrow.yaml` before adding it: the WiNet-S usually accepts only one Modbus client.

### Added

- Setup from the UI, for a WiNet-S dongle or the inverter's own LAN port, using Home Assistant's shared Modbus connection.
- Sensors for PV, AC, battery, grid, backup output and energy counters, including the values mkaiser's YAML package computes in templates. Lifetime energy counters ignore glitches that would corrupt long-term statistics.
- Power flow binary sensors.
- Controls: EMS mode, forced charge and discharge with its power, battery min and max SoC, backup reserve, battery max charge and discharge power, export power limit, backup mode, charge and discharge start power, load adjustment, and start and stop buttons.
- Battery level and charge relative to the SoC limits.
- Diagnostics with the raw register values, host and serial number removed.
- English and Swedish translations.
