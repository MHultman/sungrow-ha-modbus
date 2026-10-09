# Changelog

## Unreleased

### Changed

- A new icon: an S in a sun.

## 0.7.1 - 2026-10-09

### Added

- [More than one inverter](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/connecting.md#more-than-one-inverter) now says how to tell two inverters of the same model apart: rename each one right after adding it, entity IDs included. The migration guide covers the YAML package's multiple-inverter files and their totals.

## 0.7.0 - 2026-10-09

### Added

- **Measurement interval** under **Configure**: how often the measurements are read, from 2 seconds over the LAN port or 5 through a WiNet-S, up to 5 minutes. The form says what a shorter or longer interval costs; so does [How often it reads](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/connecting.md#how-often-it-reads).
- [Keeping your history](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/migrating-from-yaml.md#keeping-your-history) in the migration guide: giving the new entities the YAML package's entity IDs carries on their long-term statistics and Energy dashboard history. The guide used to say this was not possible.
- **Connected** and **Last reading** diagnostic entities: whether the measurements are current, and when they were read.
- A **Fix** button on the repair notice for registers the inverter refuses: it lists the entities read from them and disables them.
- **Show as unavailable when the inverter does not answer** under **Configure**, for entities to go unavailable instead of keeping the last value. Off by default.

### Changed

- Register blocks whose entities are all disabled are no longer read, which saves requests to the inverter. Enabling an entity again reads its block again.
- Entities no longer go unavailable while the inverter does not answer: they keep the last value read, and **Connected** turns off. Registers the inverter never answered show as unknown. See [When the inverter does not answer](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/troubleshooting.md#when-the-inverter-does-not-answer).
- Over the inverter's LAN port, the measurements are read every 5 seconds instead of 10, like the YAML package's fastest values. Through a WiNet-S it stays every 10 seconds.

## 0.6.3 - 2026-10-08

### Added

- A brand icon, with a variant for dark themes, shown on the integration's page in Home Assistant. Home Assistant serves it from the integration itself; the HACS store may still show a placeholder.

### Fixed

- The [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml) form opened as a blank issue: GitHub rejected it over a dropdown option it reserves. It now opens as the form.

## 0.6.2 - 2026-10-08

### Changed

- Reports filed with the [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml) form are labelled "model report". The integration itself is unchanged from 0.6.0.

## 0.6.1 - 2026-10-08

### Added

- [Testing on your inverter](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/testing.md): a checklist from the readings to every control, in an order that is safe to follow, saying how to put each setting back.
- A [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml) issue form that follows the checklist, for telling how the integration works on an inverter.

## 0.6.0 - 2026-10-08

### Added

- Repair notices under **Settings → System → Repairs**: for an inverter set up read-only because its model is not known, and for registers the inverter refuses 5 polls in a row. Each goes away by itself once it no longer applies.
- Icons for the selects, switches, buttons and the sensors without a device class. The Operating mode and Export mode icons follow the option picked.
- [Removing the integration](https://github.com/MHultman/sungrow-ha-modbus#removing-the-integration) in the README.

## 0.5.0 - 2026-10-08

### Added

- A **Force battery** action (`sungrow_modbus.force_battery`): charge, discharge or idle the battery at a given power for 1 minute to 24 hours, then go back to the self-consumption mode it started from. The end survives restarts, is retried until the inverter answers, and is cancelled by picking an operating mode by hand. The Operating mode select shows when it ends.
- [Energy managers and automations](https://github.com/MHultman/sungrow-ha-modbus/blob/main/docs/energy-managers.md): which entities and actions to use from EMHASS, Predbat, evcc or your own automations, with examples.

### Changed

- A control set to a value the inverter already holds is not written again. The setting is read back first, so a change made in iSolarCloud is never missed.

## 0.4.0 - 2026-10-08

### Added

- An **Operating mode** select: Self-consumption, Self-consumption without discharging, Battery bypass, Forced charge and Forced discharge, each setting the EMS mode, the forced command and the discharge limit in one pick. It shows the mode the inverter's settings match.
- An **Export mode** select: No limit, Zero export and Limited.
- Both remember the discharge limit and the export limit they set to 10 W and 0 W, across restarts, and write them back when leaving that option.

### Changed

- The EMS mode and battery forced charge/discharge selects are configuration entities: still on the device page, but off auto-generated dashboards.
- The README no longer compares the integration with other ones or points to the YAML package; the migration guide is still linked from the docs.

## 0.3.1 - 2026-10-08

### Changed

- The README, the documentation and the setup form say the integration has only been tested on the author's own inverter, and that it is used at your own risk: the author takes no responsibility for anything it is used for.

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
