# Python EnOcean MQTT gateway #

A Python [EnOcean](http://www.enocean.com/) gateway that exchange enocean message trough MQTT.
Allow to send formatted enocean frame to MQTT and send command to enocean equipment.

Configuration should be set into two files (`gateway.conf` and `equipments.conf`) to separate each logic.
See configuration sample to see available parameters.

Teach-in can be enabled/disabled by sending "ON"/"OFF" to `<gateway_topic>/learn`
Send enocean command by publishing MQTT json command to `<gateway_topic>/<equipment_name>/req` or `<gateway_topic>/req` with <equipment_name> in the json payload.
Command payload must be in format `{"<shortcut>": <value>}` ex: `{"CMD": 8, "PM": 2}`

Based on work of [kipe](https://github.com/kipe/enocean), [embyt](https://github.com/embyt/enocean-mqtt), [mak-gitdev](https://github.com/mak-gitdev/enocean).
## Modifications ##

- Remove Beautifulsoup4 dependencies (use ElementTree) lxml should work without effort
- Defined EEP profiles class to avoid parsing xml on fly
- Added some EEP
- Support >= 3.8 (remove OrderedDict, use f-string, use PEP 572)
- Replaced os module by pathlib
- Added descriptions to metrics
- Map unit to metrics
- Compatibility with paho-mqtt>=2.0
- Added equipment definition to facilitate EEP parsing 
- Remove usage of bit list() (`_bitarray`), replaced by direct bytearray() manipulation, improve speed and drastically memory consumption
- Publish technical metrics (rssi, last_seen, repeater)

