# SunGrow Modbus

A Home Assistant integration for Sungrow SH hybrid inverters (SH-RT, SH-T, SH-RS, SH-K and MG models) over Modbus TCP, through the inverter's own LAN port or a WiNet-S dongle. It reads the inverter's PV, battery, grid and energy values, and controls its battery and grid settings: EMS mode, forced charge and discharge, SoC limits, battery power limits, export limit and backup mode.

It is set up from the UI, and it does not open its own Modbus connection: it borrows one from Home Assistant's `modbus` integration, which keeps a single shared connection per device.

> **Status: early. Tested only on the author's own inverter**, an SH8.0RT-V112 connected through a WiNet-S. It may behave differently on yours. Settings changed here change how your battery and grid connection behave, so check each control on your own system before you automate it.

## Use at your own risk

This integration is provided as is, without warranty of any kind. It reads your inverter and changes its settings, which affects how your battery, your grid connection and your energy costs behave. **You use it entirely at your own risk. The author takes no responsibility for anything it is used for**, or for any damage, loss or cost that follows from using it, including to inverters, batteries and other equipment, their warranties, energy bills, or agreements with your grid operator.

It is not affiliated with, endorsed by or supported by Sungrow. See also the [license](LICENSE).

## Documentation

- [Supported inverters](docs/supported-inverters.md): the model families and where they differ
- [Models and entities](docs/models-and-entities.md): every known model, and which entity each family gets
- [Connecting the inverter](docs/connecting.md): LAN port or WiNet-S, enabling the LAN port, one client at a time, several inverters
- [Controls](docs/controls.md): what each control does, the EMS modes, capping the battery power
- [Energy dashboard](docs/energy-dashboard.md): which sensor goes where
- [Troubleshooting](docs/troubleshooting.md): connection problems, unavailable entities, diagnostics, logs
- [Changelog](CHANGELOG.md)

## Requirements

- Home Assistant **2026.10** or newer, which has the shared Modbus connection API this integration uses.
- A Sungrow SH hybrid inverter reachable over Modbus TCP, usually on port 502 with device ID 1. The inverter's own LAN port works better than a WiNet-S.
- Nothing else connected to the inverter over Modbus: it usually accepts one client at a time.

## Installation

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/MHultman/sungrow-ha-modbus` with type **Integration**.
3. Install **SunGrow Modbus** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and pick **SunGrow Modbus**.
5. Enter the IP address of the inverter or the WiNet-S dongle, and pick how it is connected.

Connecting through a WiNet-S takes about 15 seconds: the dongle drops requests that arrive right after a connection opens, so the integration waits before its first one.

To cap the battery power controls at what your battery should take, open **Configure** on the integration afterwards; see [Capping the battery power](docs/controls.md#capping-the-battery-power).

## What you get

One device for the inverter, named after the model it reports, such as "Sungrow SH8.0RT-V112", with:

- **Sensors**: running state, PV per MPPT, AC per phase, grid, house load, battery, backup output, smart meter values (disabled by default), daily and lifetime energy counters, and the battery level and charge relative to the SoC limits.
- **Binary sensors**: PV generating, battery charging and discharging, exporting and importing, from the inverter's power flow status.
- **Controls**: an **Operating mode** select (self-consumption, without discharging, battery bypass, forced charge, forced discharge) and an **Export mode** select (no limit, zero export, limited) that set everything in one pick, plus the separate settings behind them; see [Controls](docs/controls.md).

Entities a model does not have are not created; see [Models and entities](docs/models-and-entities.md). An inverter the integration does not recognise is set up read-only, with no controls.

The setup form, entity names and states are in English and Swedish, following Home Assistant's language setting.

## How it works

Measurements are read every 10 seconds and settings every 60, in blocks of registers rather than one request per value. A block the inverter refuses makes only its own entities unavailable. If one request goes unanswered, which the WiNet-S does now and then, the poll is retried once before the entities go unavailable.

Nothing is ever written to the inverter unless you use a control.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest --cov
```

The tests run the integration against the in-memory Modbus unit from the `modbus-connection` library, seeded with a synthetic SH8.0RT-V112.

[Models and entities](docs/models-and-entities.md) is generated from the code. After changing models, entities or their English names, regenerate it with `python -m script.generate_docs`; a test fails while it is out of date.

To release: bump `version` in `custom_components/sungrow_modbus/manifest.json`, add a section for it to `CHANGELOG.md`, push, and run the **Release** workflow under Actions.
