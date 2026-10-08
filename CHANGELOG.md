# Changelog

## 0.3.0 - 2026-10-08

From a review for anything that could harm an inverter or its statistics.

### Changed

- An inverter with a device type code the integration does not know is set up read-only: sensors only, and its settings are never read. Sungrow's SG string inverters answer the same identity registers.
- The charge and discharge start power controls, which Sungrow does not document, are only created on SH-RT models.
- The Start inverter and Stop inverter buttons are disabled by default.
- The energy counters treat their "not available" values (0xFFFF and 0xFFFFFFFF) as no reading, so one can never enter the long-term statistics.

### Added

- An optional battery max power in the integration's options, capping the forced charge/discharge power and the battery max charge and discharge power controls.
- A write that gets no answer reads the settings back at once, since it may have landed anyway.
- Documentation in `docs/`: supported inverters and how the families differ, a generated list of every model and which entities each family gets, connecting (LAN port or WiNet-S, one client at a time, several inverters), the controls and EMS modes with battery power figures for Sungrow's SBR and SBH batteries, the Energy dashboard, migrating from mkaiser's YAML package with an old-to-new entity table, and troubleshooting.

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
