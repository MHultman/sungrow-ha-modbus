# SunGrow Modbus

A Home Assistant integration for Sungrow SH hybrid inverters (SH-RS, SH-RT, SH-T and SH-K models) over Modbus TCP, through a WiNet-S dongle or the inverter's own LAN port.

It works the way Home Assistant's built-in [SolarEdge Modbus](https://www.home-assistant.io/integrations/solaredge_modbus) integration does: it is set up from the UI, and it does not open its own Modbus connection. It borrows one from Home Assistant's `modbus` integration, which keeps a single shared connection per device. There is no YAML to copy, no secrets file and no template sensors.

The register map comes from mkaiser's [Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) YAML package (see [NOTICE](NOTICE)).

> **Status: early, untested on real hardware.** So far it has only run against a simulated inverter. It reads the inverter and can change its settings: EMS mode, forced charge and discharge, SoC limits, export power limit and more. Settings changed here change how your battery and grid connection behave, so check each control on your own system before you automate it.

## Requirements

- Home Assistant **2026.10** or newer, which has the shared Modbus connection API this integration uses.
- A Sungrow SH hybrid inverter reachable over Modbus TCP, usually port 502 and device ID 1.

## Installation

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/MHultman/sungrow-ha-modbus` with type **Integration**.
3. Install **SunGrow Modbus** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and pick **SunGrow Modbus**.
5. Enter the IP address of the WiNet-S dongle or the inverter, and pick how it is connected.

Connecting through a WiNet-S takes about 15 seconds. The dongle drops requests that arrive right after a connection opens, so the integration waits before its first one.

## Moving over from the YAML package

Sungrow inverters, and the WiNet-S in particular, often accept only one Modbus TCP client at a time. Remove or comment out the `modbus:` part of `modbus_sungrow.yaml` and restart before adding this integration, or the setup will not be able to connect.

The entities get new IDs, like `sensor.sungrow_sh8_0rt_v112_battery_level`, so the Energy dashboard, automations and dashboards need pointing at them. Long-term statistics of the old entities stay where they are.

## What you get

One device for the inverter, named after the model it reports, such as "Sungrow SH8.0RT-V112".

The setup form, entity names and states are in English and Swedish, following Home Assistant's language setting.

**Sensors**
- Running state, translated, such as "Running", "Forced mode" or "Standby".
- PV: voltage, current and power per MPPT, and total DC power. MPPT 3 and 4 only on models that have them.
- AC: total active power, voltage, current and power per phase (phases B and C on three-phase models), grid frequency, inverter temperature. Reactive power and power factor are disabled by default.
- House and grid: load power, grid power (positive while importing), and import and export power split into two sensors that are never negative.
- Battery: power (positive while discharging), charging and discharging power split the same way, level, state of health, capacity, voltage, current and temperature.
- Backup output: total power, and per-phase power (disabled by default).
- Energy, daily and lifetime: PV generation, export from PV, battery charge from PV, direct consumption, battery charge and discharge, grid import and export, and house consumption.
- Smart meter values as the inverter relays them. These are only valid with the meter wired directly to the inverter, so they are disabled by default.

- Battery level and charge relative to the SoC limits, as the YAML package computes them: battery level (nominal), battery charge (nominal), battery charge (what can still be drawn before the minimum SoC) and battery charge (health-rated).

**Binary sensors**: PV generating, battery charging, battery discharging, exporting to grid and importing from grid, from the inverter's power flow status.

## Controls

| Entity | What it does |
|---|---|
| EMS mode (select) | Self-consumption, Forced, External EMS or VPP. |
| Battery forced charge/discharge (select) | Stop, Forced charge or Forced discharge. Only acted on while the EMS mode is Forced. |
| Battery forced charge/discharge power (number) | The power for forced charge or discharge, in W. |
| Battery min SoC / max SoC (numbers) | The window the battery is used in: min 0–50 %, max 50–100 %. |
| Battery max charge power / max discharge power (numbers) | Caps on battery power, from 10 W. Setting the discharge cap to 10 W keeps the battery from discharging. |
| Export power limit (switch and number) | Limits export to the grid to the number's value, within the range the inverter reports. |
| Backup mode (switch) | Keeps the backup output powered through a grid outage. |
| Battery reserved SoC for backup (number) | Charge kept back for a grid outage. |
| Battery charging start power / discharging start power (numbers) | The surplus or deficit that has to be reached before the battery starts charging or discharging. Not documented by Sungrow, so only on the SH-RT models, where they have been seen working. |
| Load adjustment mode (select) and Load adjustment (switch) | How the inverter drives a load from its DO relay. |
| Start inverter / Stop inverter (buttons) | Starts or stops the inverter. Disabled by default: enable them in the entity settings if you want them. |

The less common ones (backup reserve, start powers, load adjustment, start/stop) are configuration entities, so they stay off auto-generated dashboards.

A written value shows straight away. Settings are read back from the inverter every 60 seconds, so a change made in iSolarCloud shows within a minute. If a write gets no answer, the settings are read back at once, since it may have landed anyway.

Nothing is ever written unless you use a control: not at startup, not when Home Assistant restores its last states, not on a reconnect.

### Capping the battery power

Forced charge/discharge power and the battery max charge and discharge power go as high as the battery converter or inverter is rated for. To keep them lower, for example at what your battery's datasheet recommends, open **Settings → Devices & services → SunGrow Modbus → Configure** and set **Battery max power**. Leave it empty for no cap.

### Models it does not know

An inverter reporting a device type code that is not in the integration's model table is set up read-only: sensors only, no controls, and its settings are never read. Sungrow's SG string inverters answer the same identity registers, and the settings of an SH hybrid could mean something else on them. If yours is an SH hybrid, open an issue with its model name and the device type code from the log.

The forced charge/discharge power is in watts. Sungrow's documentation gives percent for the RT models, but RT inverters have been seen to take watts.

### The YAML package's scenes

The YAML package ships scenes for common setups. They map onto these entities like this:

| Scene | EMS mode | Forced charge/discharge | Other |
|---|---|---|---|
| Self-consumption (max battery discharge) | Self-consumption | Stop | Battery max discharge power to your battery's limit |
| Self-consumption (no battery discharge) | Self-consumption | Stop | Battery max discharge power to 10 W |
| Zero export | | | Export power limit on, at 0 W |
| Max export | | | Export power limit on, at its maximum |
| Battery bypass | Forced | Stop | |
| Battery forced charge | Forced | Forced charge | Forced power as wanted |
| Battery forced discharge | Forced | Forced discharge | Forced power as wanted |

### Left out on purpose

- **Active power limitation** (registers 13089 and 13090): the YAML package only reads these and marks them untested, and some inverters (an SH8.0RT among them) answer that they are not supported.
- **Forced startup under low SoC standby**: disabled in the YAML package because of a bug.
- **Microgrid** EMS mode: for systems without a grid connection.

### Energy dashboard

Use the lifetime (`Total …`) counters. They never go down: a lower reading is taken for a glitch and ignored, and the highest value is kept across restarts. Any lower reading would otherwise count as a meter reset, and the whole counter would be counted again in long-term statistics.

| Energy dashboard | Sensor |
|---|---|
| Grid consumption | Total import |
| Return to grid | Total export |
| Solar production | Total PV generation |
| Battery: energy into | Total battery charge |
| Battery: energy out | Total battery discharge |

## How it polls

Measurements every 10 seconds and settings every 60, in blocks of registers rather than one request per value. A block the inverter refuses makes only its own entities unavailable. If one request goes unanswered, which the WiNet-S does now and then, the poll is retried once before the entities go unavailable.

## Troubleshooting

Download the diagnostics from the device page. They contain the raw register values of every block, with the host and serial number removed, which is what it takes to work out a value a model reports differently. Attach them to an [issue](https://github.com/MHultman/sungrow-ha-modbus/issues).

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest --cov
```

The tests run the integration against the in-memory Modbus unit from the `modbus-connection` library, seeded with a synthetic SH8.0RT-V112.
