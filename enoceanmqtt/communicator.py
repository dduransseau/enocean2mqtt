# Author: Roman Morawek <roman.morawek@embyt.com>, Damien Duransseau <damien@duransseau.net>
"""this class handles the enocean and mqtt interfaces"""
import logging
import queue
import json
import platform
import time

from enocean.controller.serialcontroller import SerialController
from enocean.protocol.packet import RadioPacket
from enocean.protocol.constants import PACKET, RETURN_CODE, RORG
from equipment import Equipment
import enocean.utils
import paho.mqtt.client as mqtt


# logging.basicConfig(level=logging.DEBUG)
class Communicator:
    """the main working class providing the MQTT interface to the enocean packet classes"""
    mqtt = None
    enocean = None

    TEACH_IN_TOPIC = "gateway/teach-in"

    # Use underscore so that it is unique and doesn't match a potential future EnOcean EEP field.
    TIMESTAMP_MESSAGE_KEY = "_timestamp"
    RSSI_MESSAGE_KEY = "_rssi"

    logger = logging.getLogger('enocean.mqtt.communicator')

    def __init__(self, config, sensors):
        self.conf = config
        self.publish_timestamp = self.conf.get("publish_timestamp", True)
        self.publish_raw = self.conf.get("publish_raw")
        self.use_key_shortcut = self.conf.get("use_key_shortcut")
        # self.sensors = sensors
        self.logger.info(f"Init communicator with sensors: {sensors}, publish timestamp: {self.publish_timestamp}")
        if topic_prefix := self.conf.get("mqtt_prefix"):
            if not topic_prefix.endswith("/"):
                topic_prefix = f"{topic_prefix}/"
        else:
            topic_prefix = ""
        self.topic_prefix = topic_prefix
        self.equipments = self.setup_devices_list(topic_prefix, sensors)
        # Define set() of detected address received by the gateway
        self.detected_equipments = set()

        # check for mandatory configuration
        if 'mqtt_host' not in self.conf or 'enocean_port' not in self.conf:
            raise Exception("Mandatory configuration not found: mqtt_host/enocean_port")
        mqtt_port = int(self.conf['mqtt_port']) if 'mqtt_port' in self.conf else 1883
        mqtt_keepalive = int(self.conf['mqtt_keepalive']) if 'mqtt_keepalive' in self.conf else 60

        # setup mqtt connection
        client_id = self.conf.get('mqtt_client_id', "")
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_disconnect = self._on_disconnect
        self.mqtt.on_message = self._on_mqtt_message
        if 'mqtt_user' in self.conf:
            self.logger.info(f"authenticating: {self.conf['mqtt_user']}")
            self.mqtt.username_pw_set(self.conf['mqtt_user'], self.conf['mqtt_pwd'])
        if self.get_config_boolean('mqtt_ssl'):
            self.logger.info("enabling SSL")
            ca_certs = self.conf['mqtt_ssl_ca_certs'] if 'mqtt_ssl_ca_certs' in self.conf else None
            certfile = self.conf['mqtt_ssl_certfile'] if 'mqtt_ssl_certfile' in self.conf else None
            keyfile = self.conf['mqtt_ssl_keyfile'] if 'mqtt_ssl_keyfile' in self.conf else None
            self.mqtt.tls_set(ca_certs=ca_certs, certfile=certfile, keyfile=keyfile)
            if self.get_config_boolean('mqtt_ssl_insecure'):
                self.logger.warning("disabling SSL certificate verification")
                self.mqtt.tls_insecure_set(True)
        if self.get_config_boolean('mqtt_debug'):
            self.mqtt.enable_logger()
        if self.get_config_boolean('log_packets'):
            self.log_packets = True
        else:
            self.log_packets = False
        logging.debug("connecting to host %s, port %s, keepalive %s",
                      self.conf['mqtt_host'], mqtt_port, mqtt_keepalive)
        self.mqtt.connect_async(self.conf['mqtt_host'], port=mqtt_port, keepalive=mqtt_keepalive)
        self.mqtt.loop_start()

        # setup enocean communication
        self.enocean = SerialController(self.conf['enocean_port'], teach_in=False, timestamp=self.publish_timestamp)
        self.enocean.start()
        # sender will be automatically determined
        self.controller_address = None
        self.controller_info = None

    def __del__(self):
        if self.enocean is not None and self.enocean.is_alive():
            self.enocean.stop()

    def get_config_boolean(self, key):
        return True if self.conf.get(key, False) in ("true", "True", "1", 1, True) else False

    @classmethod
    def setup_devices_list(cls, topic_prefix, sensors):
        equipments_list = dict()
        for s in sensors:
            try:
                address = s.get("address")
                s["topic_prefix"] = topic_prefix
                equipment = Equipment(**s)
                equipments_list[address] = equipment
            except NotImplementedError as e:
                cls.logger.warning(f"Unable to setup device {address} omit")
        return equipments_list


    def get_equipment_by_topic(self, topic):
        for equipment in self.equipments.values():
            if f"{equipment.topic}/" in topic:
                return equipment

    def get_equipment(self, id):
        """ Try to get the equipement based on id (can be address or name)"""
        if equipment := self.equipments.get(id):
            return equipment
        for equipment in self.equipments.values():
            if id == equipment.name:
                return equipment

    #=============================================================================================
    # MQTT CLIENT
    #=============================================================================================
    def _on_connect(self, mqtt_client, userdata, flags, reason_code, properties):
        '''callback for when the client receives a CONNACK response from the MQTT server.'''
        if reason_code == 0:
            self.logger.info("succesfully connected to MQTT broker.")
            self.logger.debug(f"subscribe to root req topic: {self.topic_prefix}req")
            mqtt_client.subscribe(f"{self.topic_prefix}req")
            mqtt_client.subscribe(f"{self.topic_prefix}learn")
            equipments_definition_list = list()
            # listen to enocean send requests
            for equipment in self.equipments.values():
                # logging.debug("MQTT subscribing: %s", cur_sensor['name']+'/req/#')
                mqtt_client.subscribe(equipment.topic+'/req')
                equipments_definition_list.append(equipment.definition)
            mqtt_client.publish(f"{self.topic_prefix}gateway/equipments", json.dumps(equipments_definition_list), retain=True)
            # Wait that enocean communicator is initialized before publishing teach in mode
            while not self.enocean:
                time.sleep(0.1)
            try:
                teach_in = "ON" if self.enocean.teach_in else "OFF"
                mqtt_client.publish(f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", teach_in, retain=True)
            except Exception:
                self.logger.exception(Exception)
            # Subscribe to learn topic only after status is sent, to avoid two time status update

        else:
            self.logger.error(f"error connecting to MQTT broker: {reason_code}")

    def _on_disconnect(self, mqtt_client, userdata, flags, reason_code, properties):
        '''callback for when the client disconnects from the MQTT server.'''
        if reason_code == 0:
            self.logger.warning("successfully disconnected from MQTT broker")
        else:
            self.logger.warning(f"unexpectedly disconnected from MQTT broker: {reason_code}")

    def _on_mqtt_message(self, mqtt_client, userdata, msg):
        '''the callback for when a PUBLISH message is received from the MQTT server.'''
        # search for sensor
        found_topic = False
        self.logger.info("received MQTT message: %s", msg.topic)
        if msg.topic == f"{self.topic_prefix}learn":
            self.handle_learn_activation_request(msg)
        else:
            # Get how to handle MQTT message
            try:
                mqtt_payload = json.loads(msg.payload)
                try:
                    self._mqtt_message_json(msg.topic, mqtt_payload)
                except Exception as e:
                    self.logger.warning(f"unexpected or erroneous MQTT message: {msg.topic}: {msg.payload}")
                    self.logger.exception(e)

            except json.decoder.JSONDecodeError:
                self.logger.warning(f"Received message payload is not json type: {msg.payload}")
            except Exception:
                self.logger.error(f"unable to send {msg}")
                self.logger.exception(Exception)

    def handle_learn_activation_request(self, msg):
        command = msg.payload.decode("utf-8").upper()
        if command == "ON":
            self.enocean.teach_in = True
            self.logger.info(f"gateway teach in mode enabled")
            self.mqtt.publish(f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", command, retain=True)
        elif command == "OFF":
            self.enocean.teach_in = False
            self.logger.info(f"gateway teach in mode disabled ")
            self.mqtt.publish(f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", command, retain=True)
        else:
            self.logger.warning(f"not supported command: {command} for learn")

    #=============================================================================================
    # MQTT TO ENOCEAN
    #=============================================================================================

    def _mqtt_message_json(self, mqtt_topic, mqtt_json_payload):
        '''Handle received PUBLISH message from the MQTT server as a JSON payload.'''
        equipment = self.get_equipment_by_topic(mqtt_topic)
        # If the equipment is not specified in topic path, check if specified in payload
        if not equipment and mqtt_json_payload.get("equipment"):
            equipment_id = mqtt_json_payload["equipment"]
            equipment = self.get_equipment(equipment_id)
            del(mqtt_json_payload["equipment"]) # Remove key to avoid to have it during for loop
            if not equipment:
                self.logger.warning(f"unable to get equipment topic={mqtt_topic} payload={mqtt_json_payload}")
                return None
        self.logger.info(f"found equipment {equipment} for message in {mqtt_topic}")
        try:
            # JSON payload shall be sent to '/req' topic
            if mqtt_topic.endswith("/req"):
                # Parse message content
                message_params = dict()
                for key in mqtt_json_payload:
                    try:
                        # TODO: Manage to resolve the int value using profile when receive str value
                        message_params[key] = int(mqtt_json_payload[key])
                    except ValueError:
                        self.logger.debug(f"cannot parse int value for {key}: {mqtt_json_payload[key]}")
                        # Prevent storing undefined value, as it will trigger exception in EnOcean library
                        # del mqtt_json_payload[topic]

                # Append received data to cur_sensor['data'].
                # This will keep the possibility to pass single topic/payload as done with
                # normal payload, even if JSON provides the ability to pass all topic/payload
                # in a single MQTT message.
                self.logger.debug(f"{equipment.name}: req={message_params}")
                equipment.data.update(message_params)
                # Finally, send the message
                self._send_message_to_esp(equipment)
        except AttributeError:
            self.logger.warning(f"unable to handle message topic={mqtt_topic} payload={mqtt_json_payload}")

    def _send_message_to_esp(self, sensor):
        '''Send received MQTT message to EnOcean.'''
        # self.logger.debug(f"trigger message to: {sensor.name}")
        self.logger.debug(f"Message {sensor.data} to send to {sensor.address}")
        command = None
        command_shortcut = sensor.command
        if command_shortcut:
            # Check MQTT message has valid data
            if not sensor.data:
                self.logger.warning('no data to send from MQTT message!')
                return
            # Check MQTT message sets the command field
            if command_shortcut not in sensor.data or sensor.data[command_shortcut] is None:
                self.logger.warning(
                    f'command field {command_shortcut} must be set in MQTT message!')
                return
            # Retrieve command id from MQTT message
            command = sensor.data[command_shortcut]
            self.logger.debug(f'retrieved command id from MQTT message: {hex(command)}')
        self._send_packet_to_esp(sensor, command=command)
        self.logger.debug('Clearing data buffer.')
        sensor.data = {}

    #=============================================================================================
    # ENOCEAN TO MQTT
    #=============================================================================================

    def _publish_mqtt(self, equipment, mqtt_json):
        '''Publish decoded packet content to MQTT'''

        # Retain the to-be-published message ?
        retain = equipment.retain

        # Is grouping enabled on this sensor
        channel_id = equipment.channel
        channel_id = channel_id.split('/') if channel_id not in (None, '') else []

        # Determine MQTT topic
        topic = equipment.topic
        for cur_id in channel_id:
            if mqtt_json.get(cur_id) not in (None, ''):
                topic += f"/{cur_id}{mqtt_json[cur_id]}"
                del mqtt_json[cur_id]

        # Publish packet data to MQTT
        value = json.dumps(mqtt_json)
        self.logger.debug(f"{topic}: Sent MQTT: {value}")
        self.mqtt.publish(topic, value, retain=retain)
        if equipment.publish_flat:
            for prop_name, value in mqtt_json.items():
                prop_name = prop_name.replace("/", "") # Avoid sub topic if property has / ex: "I/O"
                self.mqtt.publish(f"{topic}/{prop_name}", value, retain=retain)

    def _read_esp_packet(self, packet, equipment):
        '''interpret packet, read properties and publish to MQTT'''
        self.logger.debug(f"Found equipment: {equipment}")
        if not packet.learn or equipment.log_learn:

            # Handling received data packet
            self.logger.debug(f"handle data packet {packet}, {equipment.address}")
            message = self._handle_esp_data_packet(packet, equipment)
            if not message:
                self.logger.warning(f"message not interpretable: {equipment.name}")
            else:
                # Store receive date
                if self.publish_timestamp:
                    message[self.TIMESTAMP_MESSAGE_KEY] = int(packet.received)
                if equipment.publish_rssi:
                    # Store RSSI
                    try:
                        message[self.RSSI_MESSAGE_KEY] = packet.dBm
                    except AttributeError:
                        self.logger.warning(f"Unable to set RSSI value in packet {packet}")
                self.logger.debug(f"Publish message {message}")
                self._publish_mqtt(equipment, message)
        else:
            # learn request received
            self.logger.info("learn request not emitted to mqtt")

    def _handle_esp_data_packet(self, packet, equipment):
        # data packet received
        message_payload = dict()
        if packet.packet_type == PACKET.RADIO and packet.rorg == equipment.rorg:
            # radio packet of proper rorg type received; parse EEP
            self.logger.debug(f"handle radio packet for sensor {equipment}")
            # Retrieve command from the received packet and pass it to parse_eep()
            self.logger.debug(f"try to get command for packet: {packet}")
            command = equipment.get_command_id(packet)
            # if command:
            #     self.logger.debug('retrieved command id from packet: %s', hex(command))
            # Retrieve properties from EEP
            self.logger.info(f"handle packet from {equipment.name}: {equipment.eep_code} direction={equipment.direction} command={command}")
            message = equipment.get_message_form(command=command, direction=equipment.direction)
            properties = packet.parse_message(message)
            # self.logger.debug(f"found properties in message: {properties}")

            if equipment.publish_raw or self.publish_raw:
                # Message format must be published as raw (<shortcut>: <raw_value>)
                property_key, value_key = ('shortcut', 'raw_value')
            elif equipment.use_key_shortcut or self.use_key_shortcut:
                # Message format must be published with field shortcut (<shortcut>: <value>)
                property_key, value_key = ('shortcut', 'value')
            else:
                # Message format must be published with field description (<description>: <value>) /!\ Might be verbose
                property_key, value_key = ('description', 'value')
            # loop through all EEP properties
            for prop in properties:
                # Remove / from key name to avoid sub topic issue
                key = prop[property_key]
                val = prop[value_key]
                message_payload[key] = val
                if unit := prop.get("unit"):
                    message_payload[f"{key}|unit"] = unit
        return message_payload

    #=============================================================================================
    # LOW LEVEL FUNCTIONS
    #=============================================================================================

    def _reply_packet(self, in_packet, equipment):
        '''send enocean message as a reply to an incoming message'''
        # prepare addresses
        # destination = in_packet.sender

        self._send_packet_to_esp(equipment, command=None, negate_direction=True,
                                 learn_data=in_packet.data if in_packet.learn else None)

    def _send_packet_to_esp(self, equipment, command=None,
                            negate_direction=False, learn_data=None):
        '''triggers sending of an enocean packet'''
        # determine direction indicator
        self.logger.info(f"send packet to device {equipment.name} {equipment.address}")
        direction = equipment.direction
        if negate_direction:
            # we invert the direction in this reply
            direction = 1 if direction == 2 else 2
        else:
            direction = None
        # is this a response to a learn packet?
        is_learn = learn_data is not None

        # Add possibility for the user to indicate a specific sender address
        # in sensor configuration using added 'sender' field.
        # So use specified sender address if any
        sender = enocean.utils.address_to_bytes_list(equipment.sender) if equipment.sender else self.controller_address

        try:
            packet = RadioPacket.create_message(equipment, direction=direction, command=command, sender=sender, learn=is_learn)
            self.logger.debug(f"Packet built: {packet.data}")
        except ValueError as err:
            self.logger.error(f"cannot create RF packet: {err}")
            return

        # assemble data based on packet type (learn / data)
        if is_learn:
            # learn request received
            # copy EEP and manufacturer ID
            packet.data[1:5] = learn_data[1:5]
            # update flags to acknowledge learn request
            packet.data[4] = 0xf0
        else:
            # data packet received
            # start with default data
            # Initialize packet with default_data if specified
            if equipment.default_data:
                packet.data[1:5] = [(equipment.default_data >> i * 8) &
                                    0xff for i in reversed(range(4))]
            # do we have specific data to send?
            if equipment.data:
                # override with specific data settings
                self.logger.debug(f"packet with message {packet.message}")
                packet = packet.build_message(equipment.data)
            else:
                # what to do if we have no data to send yet?
                self.logger.warning('sending only default data as answer to %s', equipment.name)
        self.enocean.send(packet)

    def _process_radio_packet(self, packet):
        # first, look whether we have this sensor configured
        sender_address = enocean.utils.combine_hex(packet.sender)
        formatted_address = enocean.utils.to_hex_string(sender_address)
        self.logger.debug(f"process radio for address {formatted_address}")
        if formatted_address not in self.detected_equipments:
            self.detected_equipments.add(formatted_address)
            self.logger.info(f"Detected new equipment with address {formatted_address}")
            # TODO: remove this and handle it trough a signal
            # self.mqtt.publish(f"{self.topic_prefix}gateway/detected_equipments", json.dumps(list(self.detected_equipments)))

        equipment = self.get_equipment(sender_address)

        # log packet, if not disabled
        if self.log_packets:
            self.logger.info(f"received: {packet}")

        # skip unknown sensor
        if not equipment:
            self.logger.info(f"unknown sensor: {enocean.utils.to_hex_string(packet.sender)}")
            return
        elif equipment.ignore:
            # skip ignored sensors
            return

        # Handling EnOcean library decision to set learn to False by default.
        # Only 1BS and 4BS are correctly handled by the EnOcean library.
        # -> VLD EnOcean devices use UTE as learn mechanism
        if equipment.rorg == RORG.VLD and packet.rorg != RORG.UTE:
            packet.learn = False
        # -> RPS EnOcean devices only send normal data telegrams.
        # Hence, learn can always be set to false
        elif equipment.rorg == RORG.RPS:
            packet.learn = False

        # interpret packet, read properties and publish to MQTT
        self._read_esp_packet(packet, equipment)

        # check for necessary reply
        if equipment.answer:
            self._reply_packet(packet, equipment)


    #=============================================================================================
    # RUN LOOP
    #=============================================================================================
    def run(self):
        """the main loop with blocking enocean packet receive handler"""
        # start endless loop for listening
        while self.enocean.is_alive():
            # Request transmitter ID, if needed
            if self.controller_address is None:
                self.enocean.init_adapter()
                self.controller_address = self.enocean._base_id
                self.logger.info(f"Base id {enocean.utils.to_hex_string(self.controller_address)}")
                # self.logger.info(f"Chip id {self.enocean._chip_id}")
                self.controller_info = self.enocean.controller_info_details
                self.logger.info(f"Controller info: {self.controller_info}")

            # Loop to empty the queue...
            try:
                # get next packet
                if platform.system() == 'Windows':
                    # only timeout on Windows for KeyboardInterrupt checking
                    packet = self.enocean.receive.get(block=True, timeout=1)
                else:
                    packet = self.enocean.receive.get(block=True)

                # check packet type
                if packet.packet_type == PACKET.RADIO:
                    self._process_radio_packet(packet)
                elif packet.packet_type == PACKET.RESPONSE:
                    response_code = RETURN_CODE(packet.data[0])
                    self.logger.info(f"got response packet: {response_code.name}")
                else:
                    self.logger.info("got non-RF packet: %s", packet)
                    continue
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                logging.debug("Exception: KeyboardInterrupt")
                break

        # Run finished, close MQTT client and stop Enocean thread
        logging.debug("Cleaning up")
        self.enocean.stop()
        self.mqtt.loop_stop()
        self.mqtt.disconnect()
        self.mqtt.loop_forever()  # will block until disconnect complete
