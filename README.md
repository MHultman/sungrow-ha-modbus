# SunGrow Modbus

A Home Assistant integration for Sungrow SH hybrid inverters (SH-RT, SH-T, SH-RS, SH-K and MG models) over Modbus TCP, through the inverter's own LAN port or a WiNet-S dongle. It reads the inverter's PV, battery, grid and energy values, and controls its battery and grid settings: EMS mode, forced charge and discharge, SoC limits, battery power limits, export limit and backup mode.

It is set up from the UI, and it does not open its own Modbus connection: it borrows one from Home Assistant's `modbus` integration, which keeps a single shared connection per device.

> **Status: early. Tested only on the author's own inverter**, an SH8.0RT-V112 connected through a WiNet-S. It may behave differently on yours. Trying it on another model? The [test checklist](docs/testing.md) and a [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml) help get it confirmed. Settings changed here change how your battery and grid connection behave, so check each control on your own system before you automate it.

## Use at your own risk

This integration is provided as is, without warranty of any kind. It reads your inverter and changes its settings, which affects how your battery, your grid connection and your energy costs behave. **You use it entirely at your own risk. The author takes no responsibility for anything it is used for**, or for any damage, loss or cost that follows from using it, including to inverters, batteries and other equipment, their warranties, energy bills, or agreements with your grid operator.

It is not affiliated with, endorsed by or supported by Sungrow. See also the [license](LICENSE).

## Documentation

- [Supported inverters](docs/supported-inverters.md): the model families and where they differ
- [Models and entities](docs/models-and-entities.md): every known model, and which entity each family gets
- [Connecting the inverter](docs/connecting.md): LAN port or WiNet-S, enabling the LAN port, one client at a time, several inverters
- [Controls](docs/controls.md): what each control does, the EMS modes, capping the battery power
- [Energy dashboard](docs/energy-dashboard.md): which sensor goes where
- [Energy managers and automations](docs/energy-managers.md): driving the inverter from EMHASS, Predbat, evcc or your own automations, and the Force battery action
- [Troubleshooting](docs/troubleshooting.md): connection problems, values that do not update, diagnostics, logs
- [Testing on your inverter](docs/testing.md): a checklist from readings to every control, and how to send a model report
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

Under **Configure** on the integration you can cap the battery power controls at what your battery should take (see [Capping the battery power](docs/controls.md#capping-the-battery-power)), and change how often the measurements are read (see [How often it reads](docs/connecting.md#how-often-it-reads)).

## What you get

One device for the inverter, named after the model it reports, such as "Sungrow SH8.0RT-V112", with:

- **Sensors**: running state, PV per MPPT, AC per phase, grid, house load, battery, backup output, smart meter values (disabled by default), daily and lifetime energy counters, the battery level and charge relative to the SoC limits, and **Last reading**, when the values were read.
- **Binary sensors**: PV generating, battery charging and discharging, exporting and importing, from the inverter's power flow status, and **Connected**, for whether the values shown are current.
- **Controls**: an **Operating mode** select (self-consumption, without discharging, battery bypass, forced charge, forced discharge) and an **Export mode** select (no limit, zero export, limited) that set everything in one pick, plus the separate settings behind them; see [Controls](docs/controls.md).
- **A Force battery action** that charges, discharges or idles the battery for a set time, then goes back to self-consumption by itself; see [Energy managers and automations](docs/energy-managers.md).

Entities a model does not have are not created; see [Models and entities](docs/models-and-entities.md). An inverter the integration does not recognise is set up read-only, with no controls.

The setup form, entity names and states are in English and Swedish, following Home Assistant's language setting.

An inverter set up read-only, and registers the inverter keeps refusing, show up as repair notices under **Settings → System → Repairs**.

## How it works

Measurements are read every 5 seconds over the LAN port and every 10 through a WiNet-S, and settings every 60, in blocks of registers rather than one request per value. A block whose entities are all disabled is not read at all. If one request goes unanswered, which the WiNet-S does now and then, the poll is retried once. When the inverter does not answer, the entities keep the last value read rather than go unavailable; **Connected** turns off, and **Last reading** says when the values were read. To have entities go unavailable instead, turn on **Show as unavailable when the inverter does not answer** under **Configure**; see [When the inverter does not answer](docs/troubleshooting.md#when-the-inverter-does-not-answer).

Nothing is ever written to the inverter unless you use a control.

## Removing the integration

1. **Leave the inverter in the state you want it in.** Removing the integration changes nothing on the inverter: it keeps the settings last written to it. Set **Operating mode** to Self-consumption, and **Export mode** to what your grid connection allows. A running **Force battery** does not end once the integration is gone.
2. Go to **Settings → Devices & services → SunGrow Modbus**, open the menu (⋮) on the entry and pick **Delete**.
3. In HACS, open **SunGrow Modbus**, pick **Remove** from its menu, and restart Home Assistant.

The entities' history and long-term statistics stay until Home Assistant purges them, or you remove them under **Developer tools → Statistics**.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest --cov
```

The tests run the integration against the in-memory Modbus unit from the `modbus-connection` library, seeded with a synthetic SH8.0RT-V112.

The brand icon in `custom_components/sungrow_modbus/brand/` is drawn from the SVGs in `script/brand/`, rendered at 256 and 512 pixels on a transparent background. Home Assistant 2026.3 and later show it on the integration. HACS's own lists do not show icons that come with a custom integration yet ([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)), and the home-assistant/brands repository no longer takes custom integrations, so they show none until HACS adds that.

[Models and entities](docs/models-and-entities.md) is generated from the code. After changing models, entities or their English names, regenerate it with `python -m script.generate_docs`; a test fails while it is out of date.

To release: bump `version` in `custom_components/sungrow_modbus/manifest.json`, add a section for it to `CHANGELOG.md`, push, and run the **Release** workflow under Actions.
