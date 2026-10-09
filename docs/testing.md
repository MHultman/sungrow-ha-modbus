# Testing on your inverter

A checklist for trying the integration on a real inverter, step by step, from reading values to the controls that change how the battery runs. Work through it once on each model and connection (LAN port or WiNet-S), then report what you found with a [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml). That is what moves a model from "expected to work" to tested.

> The controls change how your battery charges and discharges and what goes to the grid. You use them at your own risk; see [Use at your own risk](../README.md#use-at-your-own-risk). Each step below says how to put things back. Stop at the first step that does not do what it says.

## Before you start

- [ ] **Nothing else talks Modbus to the inverter**: the YAML package, Node-RED, another integration or a logger. See [Only one Modbus client at a time](connecting.md#only-one-modbus-client-at-a-time).
- [ ] **Note the current settings** in iSolarCloud, or take screenshots of them: EMS mode, SoC limits, battery max charge and discharge power, export limit, backup mode and backup reserve. These are what you put back at the end.
- [ ] **The iSolarCloud app is at hand**, so you can change a setting back without Home Assistant.
- [ ] **Pick a time** when the battery is between about 30 % and 80 %, so it can both charge and discharge, and ideally with some PV.
- [ ] **Turn on debug logging** for `custom_components.sungrow_modbus` (see [Logs](troubleshooting.md#logs)), so anything odd is in the log for the report.

## 1. Setup and readings

- [ ] Setup finishes, and the device is named after your model, such as "Sungrow SH10RT".
- [ ] The device page shows the model, the model ID (the device type code, like `0x0E0E`), the serial number and the ARM software version.
- [ ] **Settings → System → Repairs** has no notice for the inverter. If it has one, note what it says.
- [ ] Compare with iSolarCloud, or the inverter's own display, at the same moment:
  - [ ] PV power (Total DC power, and MPPT1/MPPT2 power)
  - [ ] Battery level
  - [ ] Battery power: **positive while discharging, negative while charging**
  - [ ] Grid power: **positive while importing, negative while exporting**
  - [ ] Load power (the house)
  - [ ] Daily PV generation, import, export, battery charge and discharge
- [ ] The phase B and C entities exist only on a three-phase inverter, and MPPT 3 and 4 only where the inverter has them.
- [ ] Leave it for an hour: the lifetime energy counters only go up, and **Connected** stays on, or is only off for moments.
- [ ] **Download diagnostics** from the device page works. Keep the file for the report.

## 2. Settings read back

Before changing anything, check that every control shows what iSolarCloud shows:

- [ ] Operating mode, EMS mode and battery forced charge/discharge (the last two are under **Configuration** on the device page)
- [ ] Battery min SoC and max SoC
- [ ] Battery max charge power and max discharge power
- [ ] Export power limit (switch and number) and Export mode
- [ ] Backup mode and battery reserved SoC for backup
- [ ] On SH-RT models: battery charging and discharging start power

## 3. Single settings

Change one setting at a time, check it in iSolarCloud within a minute, then set it back.

- [ ] **Battery max SoC**: lower it by 5 %, then back.
- [ ] **Battery min SoC**: raise it by 5 %, then back.
- [ ] **Battery max charge power**: lower it by 1000 W. While the battery charges, its charging power stays under the new limit. Set it back.
- [ ] **Battery max discharge power**: the same, while it discharges.
- [ ] **Export power limit**: with the switch on, lower the number by 1000 W, then back.
- [ ] **Battery reserved SoC for backup**: change it by 5 %, then back.
- [ ] **Backup mode**: only if you know what it does on your system. Turn it off and on again, or the other way round.
- [ ] On SH-RT models, **battery charging start power** and **discharging start power**: change by 100 W, then back.
- [ ] Changed in iSolarCloud instead, a setting shows in Home Assistant within about a minute.

## 4. Operating mode

Pick each option, wait a minute, and check what the battery does. Go back to **Self-consumption** after each one.

- [ ] Set **Battery forced charge/discharge power** to 1000 W first.
- [ ] **Forced charge**: the battery charges at about 1000 W (battery power about −1000 W). **This is the step that says whether your model takes the forced power in watts.** If it charges at a percentage of its maximum instead, note that in the report.
- [ ] **Forced discharge**: the battery discharges at about 1000 W.
- [ ] **Battery bypass**: the battery neither charges nor discharges.
- [ ] **Self-consumption without discharging**: **Battery max discharge power** shows 10 W, and the battery does not discharge when the house uses more than the PV makes.
- [ ] Then **Self-consumption**: **Battery max discharge power** is back at what it was before.
- [ ] In every option, EMS mode and battery forced charge/discharge (under Configuration) show the matching values, and the Operating mode icon matches the option. In the forced options, **Running state** shows Forced mode.

## 5. Export mode

- [ ] **Zero export**: with PV to spare, grid power does not go below about 0 W. Export power limit shows 0 W and its switch is on.
- [ ] **Limited**: the export power limit is back at what it was before zero export.
- [ ] **No limit**: the export power limit switch is off.
- [ ] Put it back to what it was before you started.

## 6. Force battery

Under **Developer tools → Actions**, pick **SunGrow Modbus: Force battery**.

- [ ] Charge at 1000 W for 2 minutes: Operating mode shows Forced charge, with a `forced_until` attribute 2 minutes ahead. After 2 minutes it is back to Self-consumption by itself.
- [ ] From **Self-consumption without discharging**, discharge for 2 minutes: the battery discharges at the forced power, and afterwards it is back to "without discharging", with the discharge power at 10 W again.
- [ ] Charge for 5 minutes, and restart Home Assistant straight away: after the restart it still ends at the right time.
- [ ] Charge for 5 minutes, then pick **Battery bypass** by hand: it stays in bypass after the 5 minutes.
- [ ] A power above the forced power's maximum is refused with an error, and nothing changes.

## 7. Connection

- [ ] Unplug the inverter's network cable, or restart the WiNet-S, for a few minutes: **Connected** turns off, the entities keep their last values, and **Last reading** stops moving. Afterwards it all comes back by itself.
- [ ] With **Show as unavailable when the inverter does not answer** turned on under **Configure**, the same: the entities go unavailable instead, and come back afterwards.
- [ ] Restart Home Assistant: everything comes back, and nothing is written to the inverter by the restart (its settings in iSolarCloud stay as they were).

## 8. Start and stop

Optional, and only if you want these buttons. Stopping the inverter stops PV production and the battery until it is started again.

- [ ] Enable **Stop inverter** and **Start inverter** in the entity settings.
- [ ] **Stop inverter**: **Running state** changes to Stop, and production stops.
- [ ] **Start inverter**: it starts again, which can take a few minutes.

## Afterwards

- [ ] Put every setting back to what you noted at the start, and check them in iSolarCloud.
- [ ] Open a [model report](https://github.com/MHultman/sungrow-ha-modbus/issues/new?template=model_report.yml) with the result of each section and the diagnostics file. A report that says "everything in sections 1–6 worked" is just as useful as one that lists problems.
