# Troubleshooting

## Setup says it cannot reach the inverter

Work through these in order:

1. **Something else is connected.** The inverter usually takes one Modbus client at a time. Turn off mkaiser's YAML package (its `modbus:` section) and anything else polling it, restart Home Assistant, and try again. See [Connecting the inverter](connecting.md#only-one-modbus-client-at-a-time).
2. **Wrong address or connection type.** Check the IP address in your router. Pick **WiNet-S dongle** if the address is the dongle's.
3. **The LAN port is not enabled.** See [Enabling the LAN port](connecting.md#enabling-the-lan-port).
4. **The inverter needs a cold boot.** Some only get an IP address, or start answering Modbus, after being fully powered down:
   1. Turn off the AC side.
   2. Wait 10 seconds, then switch off the battery, if there is one.
   3. Wait 10 seconds, then switch off the DC side (the large switch on the inverter).
   4. Wait at least 2 minutes, so everything inside discharges.
   5. Switch on in reverse order: DC, battery, AC.
   6. Give it 5–10 minutes to boot, then check your router for its IP address.
5. **Test Modbus outside Home Assistant.** With nothing else connected, a Modbus tool on a computer should be able to read input register 5000 (address 4999), the device type code. For example with [mbpoll](https://github.com/epsilonrt/mbpoll): `mbpoll -m tcp -a 1 -t 3 -r 5000 -c 1 <ip address>`. On Windows, [QModMaster](https://sourceforge.net/projects/qmodmaster/) does the same. If that fails too, the problem is between your network and the inverter.

"Something answered, but it is not a Sungrow hybrid inverter" means the device at that address refused the identity registers: check the address and the device ID.

## Some entities are unavailable

Some inverters, and the WiNet-S, do not serve every register. The integration reads registers in blocks, and a block the inverter refuses makes only its own entities unavailable, with a warning in the log naming the block. A block refused 5 polls in a row also gets a repair notice under **Settings → System → Repairs**, which goes away by itself if the block answers again. Single-phase SH-RS models in particular serve fewer registers. That is decided by Sungrow's firmware: disable the entities you do not need, or ignore the notice. If your model should have them, open an [issue](https://github.com/MHultman/sungrow-ha-modbus/issues) with the [diagnostics](#diagnostics).

Disabled entities (like the meter values and the per-phase backup power) are disabled on purpose; enable them in the entity settings if you want them. See [Supported inverters](supported-inverters.md#connection-makes-a-difference-too).

## Everything goes unavailable now and then

The link dropped for longer than one retry. The integration polls again every 10 seconds and recovers by itself. If it happens often on a WiNet-S:

- Make sure **Connected through** is set to **WiNet-S dongle**: it gives the dongle more time.
- Use the inverter's own LAN port instead, if it has one.
- Update the WiNet-S firmware: recent versions are much better at Modbus.
- If the connection dies and does not come back, a Modbus proxy between Home Assistant and the inverter can keep it steady. See [Connecting the inverter](connecting.md#only-one-modbus-client-at-a-time).

## A control gives an error

- **"The inverter refused the value"**: the inverter answered that it does not take that value or setting. Some models do not have every setting.
- **"Could not communicate with the inverter"**: the write got no answer. It may still have landed, so the integration reads the settings back straight away and the control shows what the inverter really holds.

## Diagnostics

On the device page, **Download diagnostics** gives a file with the raw register values of every block, what the last polls refreshed and what failed. The host and serial number are removed. It is what it takes to work out a value a model reports differently, so attach it to any [issue](https://github.com/MHultman/sungrow-ha-modbus/issues).

## Logs

**Settings → System → Logs**, and search for `sungrow_modbus`. For more detail, add this to `configuration.yaml` and restart:

```yaml
logger:
  logs:
    custom_components.sungrow_modbus: debug
```

## Firmware

Sungrow releases 1–3 inverter firmware updates a year, without a changelog. An update can change which registers the inverter serves. Updates are done through the iSolarCloud app connected locally to the inverter, or remotely through iSolarCloud with an installer account; mkaiser's [installer account guide](https://github.com/mkaiser/Sungrow-SHx-Inverter-Modbus-Home-Assistant/blob/main/doc/installer_account.md) explains how to get one. An installer account also opens settings that should not be touched without knowing exactly what they do.
