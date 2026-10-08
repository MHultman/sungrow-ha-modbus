# Migrating from the YAML package

How to move from mkaiser's [Sungrow-SHx-Inverter-Modbus-Home-Assistant](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant) YAML package to this integration. Both read the same registers, but they cannot run side by side: the inverter usually takes one Modbus client at a time.

## Steps

1. **Note what uses the old entities.** Automations, scripts, scenes, dashboards and the Energy dashboard all refer to them by entity ID. The table below says what each one becomes.
2. **Turn off the YAML package.** Remove the `modbus_sungrow` line from `packages:` in `configuration.yaml` (or comment out the `modbus:` section of `modbus_sungrow.yaml`), check the configuration, and restart Home Assistant.
3. **Add this integration**: see [Installation](../README.md#installation). Pick **WiNet-S dongle** or **the inverter's own LAN port** to match what the YAML's `host` pointed at. The YAML's `sungrow_modbus_wait_milliseconds`, `delay` and `timeout` are not needed: the connection choice sets them.
4. **Carry over the battery power limit.** If you set `sungrow_modbus_battery_max_power` in `secrets.yaml`, set the same value as **Battery max power** under **Configure**. See [Capping the battery power](controls.md#capping-the-battery-power).
5. **Point everything at the new entities**: the [Energy dashboard](energy-dashboard.md), automations, scripts, scenes and dashboards. The YAML package's scenes have equivalents in [Controls](controls.md#doing-what-the-yaml-packages-scenes-did).
6. **Clean up the old entities.** Go to **Settings → Devices & services → Entities**, filter on status *Unavailable* and integration *Modbus* (and *Template* for the YAML's template sensors), select them, and delete them. Their long-term statistics stay until you remove those under **Developer tools → Statistics**.

Long-term statistics are not joined: the new entities start their history from the day you switch.

## Entity names

New entity IDs are `<domain>.sungrow_<model>_<name>`, for example `sensor.sungrow_sh8_0rt_v112_total_import` for an SH8.0RT-V112. The table gives the new entity's name; the ID follows from it.

Two differ in more than their name:

- **Grid power** is positive while **importing**, as Home Assistant's Energy dashboard expects. The YAML's `sensor.export_power_raw` it replaces is positive while exporting.
- **Battery power** is positive while discharging, like the YAML's `sensor.battery_power` and `sensor.battery_discharging_power_signed`. There is no separate "charging power signed": it is Battery power with the sign flipped.

| YAML package | This integration |
|---|---|
| `sensor.backup_phase_a_power` | Backup phase A power |
| `sensor.backup_phase_b_power` | Backup phase B power |
| `sensor.backup_phase_c_power` | Backup phase C power |
| `sensor.battery_capacity_high_precision` | Battery capacity |
| `sensor.battery_charge` | Battery charge |
| `sensor.battery_charge_health_rated` | Battery charge (health-rated) |
| `sensor.battery_charge_nominal` | Battery charge (nominal) |
| `sensor.battery_charging_power` | Battery charging power |
| `sensor.bdc_rated_power` | Battery converter rated power |
| `sensor.battery_current` | Battery current |
| `sensor.battery_discharging_power` | Battery discharging power |
| `sensor.battery_level` | Battery level |
| `sensor.battery_level_nominal` | Battery level (nominal) |
| `sensor.battery_power` | Battery power |
| `sensor.battery_discharging_power_signed` | Battery power |
| `sensor.battery_state_of_health` | Battery state of health |
| `sensor.battery_temperature` | Battery temperature |
| `sensor.battery_voltage` | Battery voltage |
| `sensor.bms_max_charging_current` | BMS max charging current |
| `sensor.bms_max_discharging_current` | BMS max discharging current |
| `sensor.daily_battery_charge` | Daily battery charge |
| `sensor.daily_battery_charge_from_pv` | Daily battery charge from PV |
| `sensor.daily_battery_discharge` | Daily battery discharge |
| `sensor.daily_consumed_energy` | Daily consumption |
| `sensor.daily_direct_energy_consumption` | Daily direct consumption |
| `sensor.daily_exported_energy` | Daily export |
| `sensor.daily_exported_energy_from_pv` | Daily export from PV |
| `sensor.daily_imported_energy` | Daily import |
| `sensor.daily_pv_generation` | Daily PV generation |
| `sensor.daily_pv_generation_battery_discharge` | Daily PV generation and battery discharge |
| `sensor.export_power` | Export power |
| `sensor.export_power_limit_max` | Export power limit maximum |
| `sensor.export_power_limit_min` | Export power limit minimum |
| `sensor.grid_frequency` | Grid frequency |
| `sensor.export_power_raw` | Grid power |
| `sensor.import_power` | Import power |
| `sensor.inverter_temperature` | Inverter temperature |
| `sensor.load_power` | Load power |
| `sensor.meter_active_power` | Meter active power |
| `sensor.meter_phase_a_active_power` | Meter phase A active power |
| `sensor.meter_phase_a_current` | Meter phase A current |
| `sensor.meter_phase_a_voltage` | Meter phase A voltage |
| `sensor.meter_phase_b_active_power` | Meter phase B active power |
| `sensor.meter_phase_b_current` | Meter phase B current |
| `sensor.meter_phase_b_voltage` | Meter phase B voltage |
| `sensor.meter_phase_c_active_power` | Meter phase C active power |
| `sensor.meter_phase_c_current` | Meter phase C current |
| `sensor.meter_phase_c_voltage` | Meter phase C voltage |
| `sensor.mppt1_current` | MPPT1 current |
| `sensor.mppt1_power` | MPPT1 power |
| `sensor.mppt1_voltage` | MPPT1 voltage |
| `sensor.mppt2_current` | MPPT2 current |
| `sensor.mppt2_power` | MPPT2 power |
| `sensor.mppt2_voltage` | MPPT2 voltage |
| `sensor.mppt3_current` | MPPT3 current |
| `sensor.mppt3_power` | MPPT3 power |
| `sensor.mppt3_voltage` | MPPT3 voltage |
| `sensor.mppt4_current` | MPPT4 current |
| `sensor.mppt4_power` | MPPT4 power |
| `sensor.mppt4_voltage` | MPPT4 voltage |
| `sensor.phase_a_current` | Phase A current |
| `sensor.phase_a_power` | Phase A power |
| `sensor.phase_a_voltage` | Phase A voltage |
| `sensor.phase_b_current` | Phase B current |
| `sensor.phase_b_power` | Phase B power |
| `sensor.phase_b_voltage` | Phase B voltage |
| `sensor.phase_c_current` | Phase C current |
| `sensor.phase_c_power` | Phase C power |
| `sensor.phase_c_voltage` | Phase C voltage |
| `sensor.power_factor` | Power factor |
| `sensor.inverter_rated_output` | Rated output power |
| `sensor.reactive_power` | Reactive power |
| `sensor.sungrow_inverter_state` | Running state |
| `sensor.total_active_power` | Total active power |
| `sensor.total_backup_power` | Total backup power |
| `sensor.total_battery_charge` | Total battery charge |
| `sensor.total_battery_charge_from_pv` | Total battery charge from PV |
| `sensor.total_battery_discharge` | Total battery discharge |
| `sensor.total_consumed_energy` | Total consumption |
| `sensor.total_dc_power` | Total DC power |
| `sensor.total_direct_energy_consumption` | Total direct consumption |
| `sensor.total_exported_energy` | Total export |
| `sensor.total_exported_energy_from_pv` | Total export from PV |
| `sensor.total_imported_energy` | Total import |
| `sensor.total_pv_generation` | Total PV generation |
| `sensor.total_pv_generation_battery_discharge` | Total PV generation and battery discharge |
| `binary_sensor.battery_charging` | Battery charging |
| `binary_sensor.battery_discharging` | Battery discharging |
| `binary_sensor.exporting_power` | Exporting to grid |
| `binary_sensor.importing_power` | Importing from grid |
| `binary_sensor.negative_load_power` | Negative load power |
| `binary_sensor.positive_load_power` | Positive load power |
| `binary_sensor.pv_generating` | PV generating |
| `select.battery_forced_charge_discharge` | Battery forced charge/discharge |
| `select.ems_mode` | EMS mode |
| `select.load_adjustment_mode` | Load adjustment mode |
| `number.battery_charging_start_power` | Battery charging start power |
| `number.battery_discharging_start_power` | Battery discharging start power |
| `number.battery_forced_charge_discharge_power` | Battery forced charge/discharge power |
| `number.battery_max_charge_power` | Battery max charge power |
| `number.battery_max_discharge_power` | Battery max discharge power |
| `number.battery_max_soc` | Battery max SoC |
| `number.battery_min_soc` | Battery min SoC |
| `number.battery_reserved_soc_for_backup` | Battery reserved SoC for backup |
| `number.export_power_limit` | Export power limit |
| `switch.backup_mode` | Backup mode |
| `switch.export_power_limit` | Export power limit |
| `switch.load_adjustment_mode` | Load adjustment |
| `button.start_inverter` | Start inverter |
| `button.stop_inverter` | Stop inverter |

## What has no counterpart

| YAML package | Instead |
|---|---|
| `sensor.sungrow_device_type`, `sensor.sungrow_device_type_code`, `sensor.sungrow_inverter_serial` | The device page: model, model ID (the device type code) and serial number. |
| `sensor.sungrow_arm_software`, `sensor.sungrow_version_1` … `4`, firmware version sensors | The device page shows the ARM software version. Diagnostics have the DSP software too. |
| `sensor.sungrow_protocol_version` | Not read. |
| The `… raw` sensors (EMS mode, forced charge/discharge command, backup mode and so on) | The controls themselves show the state. |
| The `(delay)` binary sensors | A `for:` duration on the automation's state trigger. |
| `sensor.daily_consumed_energy_filtered` | Home Assistant's **Filter** or **Statistics** helper. |
| `switch.sungrow_dashboard_enable_danger_mode` and its automation | None; see [Controls](controls.md#left-out-on-purpose). |
| Active power limitation and APL shutdown at zero | Left out; see [Controls](controls.md#left-out-on-purpose). |
| The scenes | Your own scenes; see [Controls](controls.md#doing-what-the-yaml-packages-scenes-did). |
| The multiple-inverter YAML files | Add the integration once per inverter; see [More than one inverter](connecting.md#more-than-one-inverter). |
