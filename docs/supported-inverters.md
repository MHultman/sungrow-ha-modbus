# Supported inverters

The integration is for Sungrow's **SH hybrid inverters**: the ones with a battery input. It reads which model it is talking to from the inverter's device type code and only creates the entities that model has. The full list of models, and which entity each family gets, is in [Models and entities](models-and-entities.md).

> **Tested so far:** only on the author's own inverter, an SH8.0RT-V112 connected through a WiNet-S. You use the integration at your own risk; see [Use at your own risk](../README.md#use-at-your-own-risk). The register map is the one mkaiser's YAML package has used for years, mainly on an SH10RT over its LAN port, with SH-RS, SH-RT-V112 and SH-K-20 owners reporting partial success. If you run it on another model, an issue saying what works and what does not, with the [diagnostics](troubleshooting.md#diagnostics) attached, helps everyone.

## Families

| Family | Models | Phases | MPPTs | Notes |
|---|---|---|---|---|
| **SH-RT** | SH5.0RT to SH10RT, and their -20, -V112 and -V122 versions | 3 | 2 | The best covered family, and the only one with the charge/discharge start power controls. |
| **SH-T** | SH5T to SH25T | 3 | 3 | MPPT 3 entities. |
| **SH-RS** | SH3.0RS to SH10RS | 1 | 2, or 4 on SH8.0RS and SH10RS | Serve a smaller set of registers than the RT models, so expect some entities to stay unavailable. No start power controls (the registers are not there). |
| **SH-K** | SH3K6 to SH5K, and their -20 and -30 versions | 1 | 2 | The first generation. Little feedback so far. |
| **MG** | MG5RL, MG6RL | 1 | 2 | Little feedback so far. |

What all of them get: the PV, AC, battery, grid and energy sensors, the power flow binary sensors, and the controls (EMS mode, forced charge/discharge, SoC limits, battery power limits, export limit, backup mode, load adjustment and start/stop). Phase B and C entities are only created on the three-phase families.

## A battery is not required

Without one, the battery entities show zero or stay unknown, and the battery controls have nothing to act on. Everything else works.

## Connection makes a difference too

How the inverter is reached changes what it answers. The WiNet-S dongle serves fewer registers than the inverter's own LAN port, is slower, and drops the odd request. See [Connecting the inverter](connecting.md).

Some values are only valid in some setups:

- **Meter values** (meter active power, voltages and currents) are only valid with Sungrow's smart meter wired directly to the inverter. They are disabled by default.
- **MPPT 3 and 4** registers read as "not available" on models without them; the entities are only created where they exist.
- **Firmware version registers** are empty on many setups (the SH-RS and MG models do not serve them, and the WiNet-S often returns nothing), so the device page shows the ARM software version instead.
- **Forced charge/discharge power** is in watts on the RT models it has been checked on, although Sungrow's documentation gives percent for them. The SH-K models take watts (0–5000 W).

## Models it does not know

An inverter whose device type code is not in the model table is set up **read-only**: the sensors and binary sensors an SH-RT gets, no controls, and its settings are never read or written. Sungrow's SG string inverters (the ones without a battery) answer the same identity registers, and an SH hybrid's settings could mean something else on them. A repair notice under **Settings → System → Repairs** says when this happens, with the code.

If yours is an SH hybrid that shows up as "Unknown (0x…)", open an [issue](https://github.com/MHultman/sungrow-ha-modbus/issues) with its model name and that code.

## Not supported

- **Sungrow's SG string inverters**: they share some registers but are not hybrids; set up read-only at best.
- **iHomeManager**: it uses a different Modbus map.
- **Per-module data from SBR batteries** (cell voltages and temperatures): it lives on the battery's own Modbus device ID, not the inverter's.
- **Sungrow wallboxes and the Logger1000**: separate devices with their own maps.
- **Active power limitation** and **forced startup under low SoC standby**: see [Controls](controls.md#left-out-on-purpose).
