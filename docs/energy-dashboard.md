# Energy dashboard

Open **Settings → Dashboards → Energy** (or the Energy dashboard's edit button) and pick these sensors. The names are the entity names; the entity IDs start with `sensor.sungrow_<model>_`, for example `sensor.sungrow_sh8_0rt_v112_total_import`.

## Electricity grid

| Field | Sensor |
|---|---|
| Grid consumption | Total import |
| Return to grid | Total export |
| Grid power | Grid power (positive while importing, negative while exporting) |

## Solar panels

| Field | Sensor |
|---|---|
| Solar production energy | Total PV generation |
| Solar production power | Total DC power |

## Home battery storage

| Field | Sensor |
|---|---|
| Energy charged into the battery | Total battery charge |
| Energy discharged from the battery | Total battery discharge |
| Battery power | Battery power (positive while discharging, negative while charging) |

## Why the "Total" counters

Use the lifetime `Total …` counters rather than the daily ones. They never go down: a reading lower than one seen before is taken for a glitch and ignored, and the highest value is kept across restarts. To the energy dashboard, any lower reading is a meter reset, after which the whole counter would be counted a second time.

Both kinds also ignore the inverter's "not available" value, which would otherwise read as thousands of kWh.

## Moving over from the YAML package

To keep your energy history, give the new sensors the entity IDs the YAML sensors had: the dashboard then carries on as before, with nothing to change. See [Keeping your history](migrating-from-yaml.md#keeping-your-history). Otherwise, replace each YAML sensor with the one above; the old sensors' statistics stay in Home Assistant, but apart from the new ones.
