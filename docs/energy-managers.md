# Energy managers and automations

Anything that can control Home Assistant entities can drive the inverter: your own automations and scripts, and energy managers such as EMHASS, Predbat or evcc, whether they run as add-ons or elsewhere. They read the sensors and call actions on the controls, through Home Assistant.

> **Never let an add-on or other tool connect to the inverter over Modbus itself.** The inverter usually takes one Modbus client at a time, and the WiNet-S drops connections when a second one appears. An add-on runs in a container of its own and cannot share this integration's connection. Everything goes through Home Assistant's entities and actions. See [Only one Modbus client at a time](connecting.md#only-one-modbus-client-at-a-time).

The entity IDs below are for an inverter named "Sungrow SH8.0RT-V112". Yours start with your own inverter's name, as shown on its device page.

## What to read

| What | Entity | Notes |
|---|---|---|
| Battery level | `sensor.sungrow_sh8_0rt_v112_battery_level` | % |
| Battery power | `sensor.sungrow_sh8_0rt_v112_battery_power` | W, positive while discharging, negative while charging |
| Grid power | `sensor.sungrow_sh8_0rt_v112_grid_power` | W, positive while importing, negative while exporting |
| House load | `sensor.sungrow_sh8_0rt_v112_load_power` | W |
| PV power | `sensor.sungrow_sh8_0rt_v112_total_dc_power` | W |
| Battery capacity | `sensor.sungrow_sh8_0rt_v112_battery_capacity` | kWh |
| What the battery is doing | `select.sungrow_sh8_0rt_v112_operating_mode` | Its state is the operating mode the inverter's settings match. |

Measurements are read every 5 seconds over the LAN port and every 10 through a WiNet-S, settings every 60. A manager that needs fresher values can have the measurements read more often; see [How often it reads](connecting.md#how-often-it-reads).

## What to control

| To | Use |
|---|---|
| Charge, discharge or idle the battery for a while | The **Force battery** action, below. |
| Put the battery in a mode until told otherwise | `select.select_option` on **Operating mode**: `self_consumption`, `self_consumption_no_discharge`, `battery_bypass`, `forced_charge` or `forced_discharge`. |
| Set the forced charge or discharge power | `number.set_value` on **Battery forced charge/discharge power** |
| Stop the battery discharging, but let PV charge it | Operating mode `self_consumption_no_discharge` |
| Stop export | `select.select_option` on **Export mode**: `zero_export`, and `limited` or `no_limit` to go back |
| Limit export to a power | `number.set_value` on **Export power limit**, with Export mode `limited` |
| Cap charging or discharging power in every mode | `number.set_value` on **Battery max charge power** or **Battery max discharge power** |
| Keep a SoC range | `number.set_value` on **Battery min SoC** and **Battery max SoC** |

What each mode does is in [Controls](controls.md#operating-mode-and-export-mode).

Do not use the EMS modes **External EMS** or **VPP**: they hand the inverter to Sungrow's own energy management hardware and virtual power plant operators, not to Home Assistant. Energy managers in Home Assistant use the forced modes.

## Force battery

`sungrow_modbus.force_battery` forces the battery to charge, discharge or idle for a while, then goes back to the self-consumption mode it started from. It is the safest way for an energy manager to drive the battery: if the manager stops, crashes or loses its connection, the battery does not stay forced.

| Field | Required | What it is |
|---|---|---|
| `mode` | yes | `charge` (from PV, and from the grid if PV is not enough), `discharge` or `idle` |
| `duration` | yes | 1 minute to 24 hours |
| `power` | no | W. Left out, the forced power already set is used. Not used for `idle`. It cannot be above the **Battery forced charge/discharge power** maximum, which includes your [battery power cap](controls.md#capping-the-battery-power). |
| `config_entry_id` | with more than one inverter | The inverter to force |

```yaml
action: sungrow_modbus.force_battery
data:
  mode: charge
  power: 3000
  duration:
    minutes: 30
```

How it ends:

- **At the end of the duration** the operating mode goes back to the one it was in before: Self-consumption, or Self-consumption without discharging. If it was in another mode, it goes to Self-consumption.
- **Calling it again** replaces the running one with a new mode, power and end, and still ends in the mode the first call started from. An energy manager can call it every few minutes with a duration somewhat longer than that, and the battery goes back to self-consumption by itself if the calls stop.
- **Picking an operating mode by hand** cancels the end: the inverter stays in the mode you picked.
- **A mode changed by other means** (iSolarCloud, the separate EMS mode select) is left alone at the end.
- **If the inverter does not answer** at the end, it is tried again every minute until it does.
- **Across restarts**: the end is kept. One that passed while Home Assistant was down happens as soon as it starts again. The timer runs in Home Assistant, though: while Home Assistant is down, nothing ends the forced mode.

The Operating mode select shows a `forced_until` attribute while a forced mode is running.

## Examples

Charge from the grid in the cheapest hours, with the price from an electricity price integration:

```yaml
triggers:
  - trigger: time_pattern
    minutes: "/5"
conditions:
  - condition: numeric_state
    entity_id: sensor.electricity_price
    below: 0.05
actions:
  - action: sungrow_modbus.force_battery
    data:
      mode: charge
      power: 5000
      duration:
        minutes: 10
```

Every 5 minutes while the price is low, the forced charge is renewed for another 10. When the price rises, the calls stop and the battery is back in self-consumption within 10 minutes.

Stop exporting while the spot price is negative:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.electricity_price
    below: 0
    id: negative
  - trigger: numeric_state
    entity_id: sensor.electricity_price
    above: 0
    id: positive
actions:
  - action: select.select_option
    target:
      entity_id: select.sungrow_sh8_0rt_v112_export_mode
    data:
      option: "{{ 'zero_export' if trigger.id == 'negative' else 'limited' }}"
```

## Setting up an energy manager

Energy managers are set up with the entity IDs of the inverter's sensors and controls, often through an inverter template or a settings page:

- Point battery level, battery power, grid power, PV power and house load at the sensors in [What to read](#what-to-read). Check the sign each one expects: this integration's battery power is positive while discharging, and grid power positive while importing.
- For charging and discharging, use the Force battery action where the manager can call an action. Otherwise use the Operating mode select with the forced power number, and make sure the manager puts the mode back to `self_consumption` itself.
- Moving over from mkaiser's YAML package, a template made for its entity names needs the new names; [Migrating from the YAML package](migrating-from-yaml.md) lists which old entity became which new one.

## Writes

A control set to a value the inverter already holds is not written again. The integration reads that setting back from the inverter first, so a change made in iSolarCloud since the last read is never missed. An energy manager that sends the same values over and over costs a read each time, not a write. Even so, there is no gain in sending settings more often than once a minute.
