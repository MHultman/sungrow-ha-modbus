# SunGrow Modbus

A Home Assistant integration for Sungrow SH hybrid inverters (SH-RT, SH-T, SH-RS, SH-K and MG models) over Modbus TCP, through the inverter's own LAN port or a WiNet-S dongle. It reads the inverter's PV, battery, grid and energy values, and controls its battery and grid settings: EMS mode, forced charge and discharge, SoC limits, battery power limits, export limit and backup mode.

It works the way Home Assistant's built-in [SolarEdge Modbus](https://www.home-assistant.io/integrations/solaredge_modbus) integration does: it is set up from the UI, and it does not open its own Modbus connection. It borrows one from Home Assistant's `modbus` integration, which keeps a single shared connection per device. There is no YAML to copy, no secrets file and no template sensors.

The register map comes from mkaiser's [Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) YAML package (see [NOTICE](NOTICE)).

> **Status: early, untested on real hardware.** So far it has only run against a simulated inverter. Settings changed here change how your battery and grid connection behave, so check each control on your own system before you automate it.

## Documentation

- [Supported inverters](docs/supported-inverters.md): the model families and where they differ
- [Models and entities](docs/models-and-entities.md): every known model, and which entity each family gets
- [Connecting the inverter](docs/connecting.md): LAN port or WiNet-S, enabling the LAN port, one client at a time, several inverters
- [Controls](docs/controls.md): what each control does, the EMS modes, capping the battery power
- [Energy dashboard](docs/energy-dashboard.md): which sensor goes where
- [Migrating from the YAML package](docs/migrating-from-yaml.md): steps, and which old entity becomes which new one
- [Troubleshooting](docs/troubleshooting.md): connection problems, unavailable entities, diagnostics, logs
- [Changelog](CHANGELOG.md)

## Requirements

- Home Assistant **2026.10** or newer, which has the shared Modbus connection API this integration uses.
- A Sungrow SH hybrid inverter reachable over Modbus TCP, usually on port 502 with device ID 1. The inverter's own LAN port works better than a WiNet-S.
- Nothing else connected to the inverter over Modbus: it usually accepts one client at a time. If you use mkaiser's YAML package, see [Migrating](docs/migrating-from-yaml.md) first.

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
- **Controls**: see [Controls](docs/controls.md).

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
