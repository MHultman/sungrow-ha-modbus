# Connecting the inverter

## LAN port or WiNet-S

Most SH inverters can be reached two ways:

| | Inverter's own LAN port | WiNet-S dongle (Ethernet or Wi-Fi) |
|---|---|---|
| Registers | All the inverter serves | A subset: Sungrow restricts what the dongle relays |
| Speed | Fast | Slower; needs a gap between requests |
| Reliability | Good | Drops the odd request; busy with iSolarCloud traffic first |
| Pick in setup | **The inverter's own LAN port** | **WiNet-S dongle** |

**Use the inverter's own LAN port if your model has one.** The WiNet-S works, but it is a common source of trouble: its main job is talking to Sungrow's cloud, and Modbus comes second.

The connection choice in the setup form changes how patient the integration is:

| | LAN port | WiNet-S |
|---|---|---|
| Gap between requests | 5 ms | 30 ms |
| Timeout per request | 10 s | 30 s |
| Wait after connecting | none | 15 s |

So setting up through a WiNet-S takes about 15 seconds, and so does reconnecting after the link drops.

## Enabling the LAN port

On several inverters the LAN port has to be switched on before it answers Modbus. In the iSolarCloud app, connect to the inverter locally (**Support → Local access**, with the installer login), then go to **More → Communication settings** and enable the **inverter ETH port**. mkaiser's [FAQ](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant/blob/main/doc/faq.md#connect-the-inverter-via-ethernet) has the details and the login.

Give the inverter (or the dongle) a fixed IP address in your router, so the integration keeps finding it.

## Settings the form asks for

| Field | Usually |
|---|---|
| Host | The IP address of the LAN port or the WiNet-S |
| Connected through | LAN port or WiNet-S, see above |
| Port | 502 |
| Device ID (under More options) | 1 |

If the address changes later, use **Reconfigure** on the integration rather than adding it again: the entities, their history and their settings stay. Reconfigure checks it is still the same inverter (by serial number) before saving.

## Only one Modbus client at a time

Sungrow inverters, and the WiNet-S in particular, often accept only one Modbus TCP connection. Anything else connected to the same inverter keeps this integration from connecting, and the two take turns dropping each other:

- mkaiser's YAML package: remove or comment out its `modbus:` section and restart. See [Migrating from the YAML package](migrating-from-yaml.md).
- Other integrations, add-ons or scripts polling the inverter (evcc, SunGather, Node-RED and so on).

Within Home Assistant this is not a problem: integrations that use Home Assistant's shared Modbus connection, like this one, share a single connection per device.

If several programs need the inverter, put a Modbus proxy in front of it, such as the [modbus-proxy add-on](https://github.com/Akulatraxas/ha-modbusproxy), and point every program, this integration included, at the proxy.

## More than one inverter

Add the integration once per inverter. Each gets its own device, named after its model, and its own entities. Inverters behind the same address with different device IDs share one connection.

To add up values across inverters, for example total PV power, use Home Assistant's **Combine the state of several sensors** helper (Settings → Devices & services → Helpers), set to *Sum*.
