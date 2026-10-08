# SunGrow Modbus

A Home Assistant integration for Sungrow SH hybrid inverters (SH-RS, SH-RT, SH-T and SH-K models) over Modbus TCP, through a WiNet-S dongle or the inverter's own LAN port.

It works the way Home Assistant's built-in [SolarEdge Modbus](https://www.home-assistant.io/integrations/solaredge_modbus) integration does: it is set up from the UI, and it does not open its own Modbus connection. It borrows one from Home Assistant's `modbus` integration, which keeps a single shared connection per device. There is no YAML to copy, no secrets file and no template sensors.

The register map comes from mkaiser's [Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) YAML package (see [NOTICE](NOTICE)).

> **Status: read-only.** This version reads the inverter and does not write to it. The controls the YAML package has (EMS mode, forced charge and discharge, SoC limits, export power limit, backup mode) are not here yet.

## Requirements

- Home Assistant **2026.10** or newer, which has the shared Modbus connection API this integration uses.
- A Sungrow SH hybrid inverter reachable over Modbus TCP, usually port 502 and device ID 1.

## Installation

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/MHultman/sungrow-modbus` with type **Integration**.
3. Install **SunGrow Modbus** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and pick **SunGrow Modbus**.
5. Enter the IP address of the WiNet-S dongle or the inverter, and pick how it is connected.

Connecting through a WiNet-S takes about 15 seconds. The dongle drops requests that arrive right after a connection opens, so the integration waits before its first one.

## Moving over from the YAML package

Sungrow inverters, and the WiNet-S in particular, often accept only one Modbus TCP client at a time. Remove or comment out the `modbus:` part of `modbus_sungrow.yaml` and restart before adding this integration, or the setup will not be able to connect.

The entities get new IDs, like `sensor.sungrow_sh8_0rt_v112_battery_level`, so the Energy dashboard, automations and dashboards need pointing at them. Long-term statistics of the old entities stay where they are.

## What you get

One device for the inverter, named after the model it reports, such as "Sungrow SH8.0RT-V112".

**Sensors**
- Running state, translated, such as "Running", "Forced mode" or "Standby".
- PV: voltage, current and power per MPPT, and total DC power. MPPT 3 and 4 only on models that have them.
- AC: total active power, voltage, current and power per phase (phases B and C on three-phase models), grid frequency, inverter temperature. Reactive power and power factor are disabled by default.
- House and grid: load power, grid power (positive while importing), and import and export power split into two sensors that are never negative.
- Battery: power (positive while discharging), charging and discharging power split the same way, level, state of health, capacity, voltage, current and temperature.
- Backup output: total power, and per-phase power (disabled by default).
- Energy, daily and lifetime: PV generation, export from PV, battery charge from PV, direct consumption, battery charge and discharge, grid import and export, and house consumption.
- Smart meter values as the inverter relays them. These are only valid with the meter wired directly to the inverter, so they are disabled by default.

**Binary sensors**: PV generating, battery charging, battery discharging, exporting to grid and importing from grid, from the inverter's power flow status.

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

Every 10 seconds, in blocks of up to 48 registers at a time rather than one request per value. A block the inverter refuses makes only its own entities unavailable. If one request goes unanswered, which the WiNet-S does now and then, the poll is retried once before the entities go unavailable.

## Troubleshooting

Download the diagnostics from the device page. They contain the raw register values of every block, with the host and serial number removed, which is what it takes to work out a value a model reports differently. Attach them to an [issue](https://github.com/MHultman/sungrow-modbus/issues).

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest --cov
```

The tests run the integration against the in-memory Modbus unit from the `modbus-connection` library, seeded with a synthetic SH8.0RT-V112.
