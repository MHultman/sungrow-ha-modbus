# Controls

The controls change how your inverter runs the battery and the grid connection. They write the same registers, with the same values, as mkaiser's YAML package. Nothing is ever written unless you use one: not at startup, not when Home Assistant restores its last states, not on a reconnect.

> Changing these settings changes how your battery charges and discharges and what goes to the grid. Check each one on your own system before you automate it. The controls have only been tested on the author's own inverter, and you use them at your own risk; see [Use at your own risk](../README.md#use-at-your-own-risk).

## What there is

| Entity | Type | What it does |
|---|---|---|
| Operating mode | select | How the battery runs, in one pick. See [Operating mode and export mode](#operating-mode-and-export-mode). |
| Export mode | select | No limit, zero export, or limited to the export power limit. |
| EMS mode | select | How the inverter runs the battery, see [EMS modes](#ems-modes). |
| Battery forced charge/discharge | select | Stop, Forced charge or Forced discharge. Only acted on while the EMS mode is Forced. |
| Battery forced charge/discharge power | number | The power for forced charge or discharge, in W. |
| Battery min SoC | number | The lowest charge the battery is used down to, 0–50 %. |
| Battery max SoC | number | The highest charge the battery is charged to, 50–100 %. |
| Battery max charge power | number | A cap on charging power, from 10 W. |
| Battery max discharge power | number | A cap on discharging power, from 10 W. At 10 W the battery effectively does not discharge. |
| Export power limit | switch | Whether export to the grid is limited. |
| Export power limit | number | The limit, within the range the inverter reports. |
| Backup mode | switch | Keeps the backup output powered through a grid outage. |
| Battery reserved SoC for backup | number | Charge kept back for a grid outage. |
| Battery charging start power | number | The surplus PV that has to be there before the battery starts charging. SH-RT only. |
| Battery discharging start power | number | The deficit that has to be there before the battery starts discharging. SH-RT only. |
| Load adjustment mode | select | How the inverter drives a load from its DO relay: Timing, On/off, Power optimization or Disabled. |
| Load adjustment | switch | Whether the DO relay load control is on. |
| Start inverter / Stop inverter | button | Starts or stops the inverter. **Disabled by default**: enable them in the entity settings if you want them. |

EMS mode, battery forced charge/discharge, backup reserve, the start powers, load adjustment and start/stop are configuration entities, so they stay off auto-generated dashboards. They are still on the device page, under Configuration. Which models get which control is in [Models and entities](models-and-entities.md#entities).

A value you set shows straight away. Settings are read back from the inverter every 60 seconds, so a change made in iSolarCloud shows within a minute. A write that gets no answer has the settings read back at once, since it may have landed anyway. A value the inverter refuses gives an error, and the old value stays.

## Operating mode and export mode

The two selects set everything a common setup needs in one pick, so there is nothing to build yourself. Use them on a dashboard, or from an automation with the `select.select_option` action, for example to charge on a cheap tariff.

**Operating mode**

| Option | What it sets |
|---|---|
| Self-consumption | EMS mode Self-consumption, forced command Stop, and gives back the battery max discharge power if it was held at 10 W. |
| Self-consumption without discharging | EMS mode Self-consumption, forced command Stop, and battery max discharge power 10 W: PV still charges the battery, but the battery does not discharge. |
| Battery bypass | EMS mode Forced, command Stop: the battery idles. |
| Forced charge | EMS mode Forced, command Forced charge, at **Battery forced charge/discharge power**. Charges from PV, and from the grid if PV is not enough. |
| Forced discharge | EMS mode Forced, command Forced discharge, at **Battery forced charge/discharge power**, and gives back the battery max discharge power first if it was held at 10 W. |

**Export mode**

| Option | What it sets |
|---|---|
| No limit | Export power limit off. |
| Zero export | Export power limit 0 W, then on. |
| Limited | Export power limit on, at the limit it had before zero export was picked. With nothing to go back to, the highest limit the inverter allows. |

How they behave:

- **They show what the inverter is doing.** The option is worked out from the inverter's settings, so a change made in iSolarCloud or with the separate controls shows too. Settings that match no option, like the EMS mode set to VPP, show as unknown.
- **Your own limits are kept.** Before "without discharging" sets the discharge power to 10 W, and before zero export sets the export limit to 0 W, the value you had is remembered, across restarts too, and written back when you pick an option that needs it. With nothing remembered (the setting was already 10 W or 0 W when the integration first saw it), the discharge power goes back to its maximum, held to your [battery power cap](#capping-the-battery-power), and the export limit to the highest the inverter allows.
- **Only what changes is written**, one setting at a time. If the inverter refuses one, you get an error and the settings after it are not written. The select then shows what the inverter really holds, often unknown, until you pick an option again.
- **The inverter stays in the mode you picked** until you pick another. After a forced charge or discharge, pick Self-consumption again.
- Forced charge keeps the discharge power as it was, so the battery still does not discharge afterwards if you came from "without discharging".

## EMS modes

| Mode | What the inverter does |
|---|---|
| **Self-consumption** | The default. PV covers the house first, the surplus charges the battery, the battery covers the house when PV is not enough, and only what is left goes to or comes from the grid. |
| **Forced** | The battery does what **Battery forced charge/discharge** says, at **Battery forced charge/discharge power**: charge (from PV, and from the grid if PV is not enough), discharge (to the house, and to the grid beyond that), or stop (the battery idles, which is the "battery bypass" mode). |
| **External EMS** | The inverter waits for an external energy management system to command it. |
| **VPP** | The inverter takes commands from a virtual power plant operator. |

The SoC limits and the battery max charge and discharge power apply in every mode.

## Capping the battery power

The forced charge/discharge power and the battery max charge and discharge power go as high as the battery converter or the inverter is rated for. The inverter and the battery's BMS still enforce the battery's real limits, but staying below them is gentler on the battery: Sungrow's technical trainings recommend the low end of the battery's voltage range times its rated current, rather than the nominal voltage.

To cap the three controls, open **Settings → Devices & services → SunGrow Modbus → Configure** and set **Battery max power**. Leave it empty for no cap. For Sungrow's own batteries, from their datasheets ([SBR](https://info-support.sungrowpower.com/application/pdf/2024/09/13/DS_20240907_SBR064_096_128_160_192_224_256_Datasheet_V5_EN.pdf), [SBH](https://info-support.sungrowpower.com/application/pdf/2024/08/30/DS_20240329_SBH100_150_200_250_300_350_400_Datasheet_V4_EN.pdf)):

| Battery | Conservative | Nominal |
|---|---|---|
| SBR064 | 3240 W | 3840 W |
| SBR096 | 4860 W | 5760 W |
| SBR128 | 6480 W | 7680 W |
| SBR160 | 8100 W | 9600 W |
| SBR192 | 9720 W | 11520 W |
| SBR224 | 11340 W | 13440 W |
| SBR256 | 12960 W | 15360 W |
| SBH100 | 5940 W | 7040 W |
| SBH150 | 8910 W | 10560 W |
| SBH200 | 11880 W | 14080 W |
| SBH250 | 14850 W | 17600 W |
| SBH300 | 17820 W | 21120 W |
| SBH350 | 20790 W | 24640 W |
| SBH400 | 23760 W | 28160 W |

For other batteries, check their datasheet.

## Left out on purpose

- **Active power limitation** (Sungrow registers 13089 and 13090): the YAML package only reads these and marks them untested, and some inverters answer that they are not supported.
- **Forced startup under low SoC standby**: disabled in the YAML package because of a bug.
- **Microgrid** EMS mode: for systems without a grid connection.
- **A "danger mode" lock** like the YAML package's dashboard switch: Home Assistant entities have no such thing. Put the controls on a dashboard of their own, or use a confirmation on the cards, if you worry about accidental changes.
