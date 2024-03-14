# Python EnOcean MQTT gateway #

A Python library for reading and controlling [EnOcean](http://www.enocean.com/) devices trough MQTT.

Based on work of [kipe](https://github.com/kipe/enocean), [embyt](https://github.com/embyt/enocean-mqtt), [mak-gitdev](https://github.com/mak-gitdev/enocean).

## Modifications ##


- Remove Beautifulsoup4 dependencies (use ElementTree) lxml should work without effort
- Defined EEP profiles class to avoid parsing xml on fly
- Added some EEP
- Support >= 3.8 (remove OrderedDict, use f-string, use PEP 572)
- Replaced os module by pathlib
- Added descriptions to metrics
- Compatibility with paho-mqtt>=2.0
