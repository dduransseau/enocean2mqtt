# Author: Damien Duransseau <damien@duransseau.net> based on Roman Morawek <roman.morawek@embyt.com> work
"""this class handles the enocean and mqtt interfaces"""
import logging
import queue
import json
import platform
import time

from enocean.controller.serialcontroller import SerialController
from enocean.protocol.packet import RadioPacket
from enocean.protocol.constants import PacketTyoe, ReturnCode, RORG, DataFieldType, SpecificShortcut, FieldSetName
from equipment import Equipment
import enocean.utils
import paho.mqtt.client as mqtt


class Communicator:
    """the main working class providing the MQTT interface to the enocean packet classes"""
    mqtt_client = None
    enocean = None

    TEACH_IN_TOPIC = "_gateway/teach-in"
    ADAPTER_DETAILS_TOPIC = "_gateway/adapter"
    GATEWAY_STATUS_TOPIC = "_gateway/status"
    GATEWAY_EQUIPMENTS_TOPIC = "_gateway/equipments"
    # Use underscore so that it is unique and doesn't match a potential future EnOcean EEP field.
    TIMESTAMP_MESSAGE_KEY = "_timestamp"
    RSSI_MESSAGE_KEY = "_rssi"
    CHANNEL_MESSAGE_KEY = "_channel"
    RORG_MESSAGE_KEY = "_rorg"

    logger = logging.getLogger('enocean.mqtt.communicator')

    def __init__(self, config):
        self.conf_manager = config
        self.conf = self.conf_manager.global_config
        self.publish_timestamp = self.conf.get("publish_timestamp", True)
        self.publish_raw = self.get_config_boolean("publish_raw")
        self.publish_internal = self.get_config_boolean("publish_internal")
        self.publish_response_status = self.get_config_boolean("publish_response_status")
        self.use_key_shortcut = self.conf.get("use_key_shortcut")
        if topic_prefix := self.conf.get("mqtt_prefix"):
            if not topic_prefix.endswith("/"):
                topic_prefix = f"{topic_prefix}/"
        else:
            topic_prefix = ""
        self.topic_prefix = topic_prefix
        self.logger.info(
            f"Init communicator with sensors: {self.conf_manager.sensors}, publish timestamp: {self.publish_timestamp}")
        self.equipments = dict()
        # Set self.equipments based on sensors present in config_manager
        self.setup_devices_list()
        # Define set() of detected address received by the gateway
        self.detected_equipments = set()

        # check for mandatory configuration
        if 'mqtt_host' not in self.conf or 'enocean_port' not in self.conf:
            raise Exception("Mandatory configuration not found: mqtt_host/enocean_port")
        mqtt_port = int(self.conf['mqtt_port']) if self.conf.get('mqtt_port') else 1883
        mqtt_keepalive = int(self.conf['mqtt_keepalive']) if self.conf.get('mqtt_keepalive') else 60

        # setup enocean connection
        self.enocean = SerialController(self.conf['enocean_port'], teach_in=False, timestamp=self.publish_timestamp)
        self.enocean.start()
        # sender will be automatically determined
        self.controller_address = None
        self.controller_info = None

        # setup mqtt connection
        client_id = self.conf.get('mqtt_client_id', "enocean2mqtt")
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message
        if 'mqtt_user' in self.conf:
            self.logger.info(f"authenticating: {self.conf['mqtt_user']}")
            self.mqtt_client.username_pw_set(self.conf['mqtt_user'], self.conf['mqtt_pwd'])
        if self.get_config_boolean('mqtt_ssl'):
            self.logger.info("enabling SSL")
            ca_certs = self.conf['mqtt_ssl_ca_certs'] if 'mqtt_ssl_ca_certs' in self.conf else None
            certfile = self.conf['mqtt_ssl_certfile'] if 'mqtt_ssl_certfile' in self.conf else None
            keyfile = self.conf['mqtt_ssl_keyfile'] if 'mqtt_ssl_keyfile' in self.conf else None
            self.mqtt_client.tls_set(ca_certs=ca_certs, certfile=certfile, keyfile=keyfile)
            if self.get_config_boolean('mqtt_ssl_insecure'):
                self.logger.warning("disabling SSL certificate verification")
                self.mqtt_client.tls_insecure_set(True)
        if self.get_config_boolean('mqtt_debug'):
            self.mqtt_client.enable_logger()
        self.log_packets = self.get_config_boolean('log_packets')
        logging.debug(f"connecting to host {self.conf['mqtt_host']}, port {mqtt_port}, keepalive {mqtt_keepalive}")
        self.mqtt_qos = int(self.conf['mqtt_qos']) if self.conf.get('mqtt_qos') else 0
        self.mqtt_client.connect_async(self.conf['mqtt_host'], port=mqtt_port, keepalive=mqtt_keepalive)
        self.mqtt_client.loop_start()

    def __del__(self):
        if self.enocean is not None and self.enocean.is_alive():
            self.enocean.stop()

    def get_config_boolean(self, key):
        return True if self.conf.get(key, False) in ("true", "True", "1", 1, True) else False

    def setup_devices_list(self, force=False):
        equipments_list = dict()
        if force:
            self.conf_manager.load_config_file(omit_global=True)
        for s in self.conf_manager.sensors:
            address = s.get("address")
            try:
                s["topic_prefix"] = self.topic_prefix
                equipment = Equipment(**s)
                equipments_list[address] = equipment
            except NotImplementedError:
                self.logger.warning(f"Unable to setup device {address}")
        self.equipments = equipments_list

    def get_equipment_by_topic(self, topic):
        for equipment in self.equipments.values():
            if f"{equipment.topic}/" in topic:
                return equipment

    def get_equipment(self, id):
        """ Try to get the equipment based on id (can be address or name)"""
        if equipment := self.equipments.get(id):
            return equipment
        for equipment in self.equipments.values():
            if id == equipment.name:
                return equipment
        self.logger.warning(f"Unable to find equipment with key {id}")

    @property
    def equipments_definition_list(self):
        equipments_definition_list = list()
        # listen to enocean send requests
        for equipment in self.equipments.values():
            equipments_definition_list.append(equipment.definition)
        return equipments_definition_list

    # =============================================================================================
    # MQTT CLIENT
    # =============================================================================================

    def mqtt_publish(self, topic, payload, retain=False, qos=0):
        # Helper that publish mqtt message using global config and handling dict as json
        qos = qos or self.mqtt_qos
        if isinstance(payload, dict) or isinstance(payload, list):
            payload = json.dumps(payload)
        self.mqtt_client.publish(topic, payload, retain=retain, qos=qos)

    def _on_connect(self, mqtt_client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.logger.info("successfully connected to MQTT broker.")
            self.logger.debug(f"subscribe to root req topic: {self.topic_prefix}req")
            mqtt_client.subscribe(f"{self.topic_prefix}req")
            mqtt_client.subscribe(f"{self.topic_prefix}learn")
            mqtt_client.subscribe(f"{self.topic_prefix}reload")
            if self.publish_internal:
                self.mqtt_publish(f"{self.topic_prefix}{self.GATEWAY_STATUS_TOPIC}", "ONLINE", retain=True)
                # listen to enocean send requests
                for equipment in self.equipments.values():
                    # logging.debug("MQTT subscribing: %s", cur_sensor['name']+'/req/#')
                    mqtt_client.subscribe(equipment.topic+'/req')
                self.mqtt_publish(f"{self.topic_prefix}{self.GATEWAY_EQUIPMENTS_TOPIC}", self.equipments_definition_list, retain=True)
                self._publish_gateway_adapter_details()
        else:
            self.logger.error(f"error connecting to MQTT broker: {reason_code}")

    def _publish_gateway_adapter_details(self):
        # Wait that enocean communicator is initialized before publishing teach in mode
        for i in range(10):
            if self.enocean:
                break
            time.sleep(0.1)
        try:
            teach_in = "ON" if self.enocean.teach_in else "OFF"
            self.mqtt_publish(f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", teach_in, retain=True)
            for i in range(10):
                if self.controller_info and self.controller_address:
                    break
                time.sleep(0.1)
            payload = self.controller_info
            payload["address"] = enocean.utils.to_hex_string(self.controller_address)
            self.mqtt_publish(f"{self.topic_prefix}{self.ADAPTER_DETAILS_TOPIC}", payload, retain=True)
        except Exception:
            self.logger.exception(Exception)

    def _on_disconnect(self, mqtt_client, userdata, flags, reason_code, properties):
        '''callback for when the client disconnects from the MQTT server.'''
        if reason_code == 0:
            self.logger.info("successfully disconnected from MQTT broker")
        else:
            self.logger.warning(f"unexpectedly disconnected from MQTT broker: {reason_code}")

    def _on_mqtt_message(self, mqtt_client, userdata, msg):
        # search for sensor
        self.logger.info("received MQTT message: %s", msg.topic)
        if msg.topic == f"{self.topic_prefix}learn":
            self.handle_learn_activation_request(msg)
        elif msg.topic == f"{self.topic_prefix}reload":
            self.logger.info("Reload equipments list")
            self.setup_devices_list(force=True)
            self.mqtt_publish(f"{self.topic_prefix}{self.GATEWAY_EQUIPMENTS_TOPIC}", self.equipments_definition_list, retain=True)
            self.logger.debug(f"New equipments list {self.equipments}")
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
        elif command == "OFF":
            self.enocean.teach_in = False
            self.logger.info(f"gateway teach in mode disabled ")
        else:
            self.logger.warning(f"not supported command: {command} for learn")
            return
        if self.publish_internal:
            self.mqtt_publish(f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", command, retain=True)

    # =============================================================================================
    # MQTT TO ENOCEAN
    # =============================================================================================

    def _mqtt_message_json(self, mqtt_topic, mqtt_json_payload):
        '''Handle received PUBLISH message from the MQTT server as a JSON payload.'''
        equipment = self.get_equipment_by_topic(mqtt_topic)
        # If the equipment is not specified in topic path, check if specified in payload
        if not equipment:
            try:
                equipment_id = mqtt_json_payload["equipment"]
                equipment = self.get_equipment(equipment_id)
                del mqtt_json_payload["equipment"]  # Remove key to avoid to have it during for loop
            except KeyError:
                self.logger.warning(f"unable to get equipment topic={mqtt_topic} payload={mqtt_json_payload}")
                return None
        self.logger.debug(f"found {equipment} for message in {mqtt_topic}")
        try:
            # JSON payload shall be sent to '/req' topic
            if mqtt_topic.endswith("/req"):
                self._handle_mqtt_message(equipment, mqtt_json_payload)
        except AttributeError:
            self.logger.warning(f"unable to handle message topic={mqtt_topic} payload={mqtt_json_payload}")

    def _handle_mqtt_message(self, equipment, payload):
        '''Send received MQTT message to EnOcean.'''
        self.logger.debug(f"Message {payload} to send to {equipment.address}")
        # Check MQTT message has valid data
        if not payload:
            self.logger.warning('no data to send from MQTT message!')
            return
        command_id = None
        command_shortcut = equipment.command  # Get the command shortcut used by the device (commonly "CMD")
        if command_shortcut:
            # Check MQTT message sets the command field and set the command id
            if command_id := payload.get(command_shortcut):
                self.logger.debug(f'retrieved command id from MQTT message: {hex(command_id)}')
            else:
                self.logger.warning(f'command field {command_shortcut} must be set in MQTT message!')
                return
        self._send_packet_to_esp(equipment, data=payload, command=command_id)
        self.logger.debug('Clearing data buffer.')

    # =============================================================================================
    # ENOCEAN TO MQTT
    # =============================================================================================

    def _publish_mqtt(self, equipment, mqtt_json):
        '''Publish decoded packet content to MQTT'''
        # Retain the to-be-published message ?
        retain = equipment.retain
        # Determine MQTT topic
        topic = equipment.topic

        # Is grouping enabled on this sensor
        if self.CHANNEL_MESSAGE_KEY in mqtt_json.keys():
            topic += f'/{mqtt_json[self.CHANNEL_MESSAGE_KEY]}'
            # del mqtt_json[self.CHANNEL_MESSAGE_KEY]

        # Publish packet data to MQTT
        self.logger.debug(f"{topic}: Sent MQTT: {mqtt_json}")
        self.mqtt_publish(topic, mqtt_json, retain=retain)
        if equipment.publish_flat:
            for prop_name, value in mqtt_json.items():
                prop_name = prop_name.replace("/", "")  # Avoid sub topic if property has / ex: "I/O"
                self.mqtt_publish(f"{topic}/{prop_name}", value, retain=retain)

    def _parse_esp_packet(self, packet, equipment):
        '''interpret packet, read properties and publish to MQTT'''
        if not packet.learn or equipment.log_learn:
            # Handling received data packet
            message_fields = self._handle_esp_data_packet(packet, equipment)
            if not message_fields:
                self.logger.warning(f"message not interpretable: {equipment.name}")
            else:
                # Store receive date
                if self.publish_timestamp:
                    message_fields[self.TIMESTAMP_MESSAGE_KEY] = int(packet.received)
                if equipment.publish_rssi:
                    # Store RSSI
                    try:
                        message_fields[self.RSSI_MESSAGE_KEY] = packet.dBm
                    except AttributeError:
                        self.logger.warning(f"Unable to set RSSI value in packet {packet}")
                message_fields[self.RORG_MESSAGE_KEY] = packet.rorg
                self.logger.debug(f"Publish message {message_fields}")
                self._publish_mqtt(equipment, message_fields)
        elif packet.learn and not self.enocean.teach_in:
            self.logger.info("Received teach-in packet but learn is not enabled")
        else:
            # learn request received
            self.logger.info("learn request not emitted to mqtt")

    def _handle_esp_data_packet(self, packet, equipment):
        # data packet received
        if packet.packet_type == PacketTyoe.RADIO and packet.rorg == equipment.rorg:
            # radio packet of proper rorg type received; parse EEP
            self.logger.debug(f"handle radio packet for sensor {equipment}")
            fields = equipment.get_packet_fields(packet, direction=equipment.direction)
            properties = packet.parse_message(fields)
            # self.logger.debug(f"found properties in message: {properties}")
            return self.format_enocean_message(properties, equipment)

    def format_enocean_message(self, parsed_message, equipment):
        """
        parsed_message: list of EEP dict() field
        equipment: equipment linked that sent message

        return: dict() with formatted fields and units
        """
        message_payload = dict()
        value_fields = list()
        operator_fields = list()
        unit_fields = list()
        # Define the key that should be used in field to compose json message
        if equipment.publish_raw or self.publish_raw:
            # Message format must be published as raw (<shortcut>: <raw_value>)
            property_key, value_key = (FieldSetName.SHORTCUT, FieldSetName.RAW_VALUE)
        elif equipment.use_key_shortcut or self.use_key_shortcut:
            # Message format must be published with field shortcut (<shortcut>: <value>)
            property_key, value_key = (FieldSetName.SHORTCUT, FieldSetName.VALUE)
        else:
            # Message format must be published with field description (<description>: <value>) /!\ Might be verbose
            property_key, value_key = (FieldSetName.DESCRIPTION, FieldSetName.VALUE)
        # loop through all EEP properties
        for prop in parsed_message:
            # Remove not supported fields # TODO: might be improve
            if isinstance(prop[FieldSetName.VALUE], str) and "not supported" in prop[FieldSetName.VALUE]:
                continue
            # Manage to calculate value before send
            if prop[FieldSetName.TYPE] == DataFieldType.VALUE:
                value_fields.append(prop)
            elif prop[FieldSetName.SHORTCUT] in (SpecificShortcut.MULTIPLIER, SpecificShortcut.DIVISOR):
                operator_fields.append(prop)
            elif prop[FieldSetName.SHORTCUT] == SpecificShortcut.UNIT:
                unit_fields.append(prop)
            key = prop[property_key]
            val = prop[value_key]
            message_payload[key] = val
            # Add unit of value fields
            if unit := prop.get(FieldSetName.UNIT):
                message_payload[f"{key}|unit"] = unit
            # Set specific channel is set for this equipment and set it as internal value
            if prop[FieldSetName.SHORTCUT] == equipment.channel:
                message_payload[self.CHANNEL_MESSAGE_KEY] = prop[FieldSetName.VALUE]
        return message_payload


    # =============================================================================================
    # LOW LEVEL FUNCTIONS
    # =============================================================================================

    def _reply_packet(self, in_packet, equipment):
        '''send enocean message as a reply to an incoming message'''
        # prepare addresses
        # destination = in_packet.sender
        self._send_packet_to_esp(equipment, data=equipment.answer, command=None, negate_direction=True,
                                 learn_data=in_packet.data if in_packet.learn else None)

    def _send_packet_to_esp(self, equipment, data=None, command=None, negate_direction=False, learn_data=None):
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
            packet = RadioPacket.create_message(equipment, direction=direction,
                                                command=command, sender=sender, learn=is_learn)
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
            if data:
                # override with specific data settings
                self.logger.debug(f"packet with message {packet.message}")
                packet = packet.build_message(data)
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
            # self.mqtt_publish(f"{self.topic_prefix}gateway/detected_equipments", list(self.detected_equipments))
        # log packet, if not disabled
        # if self.log_packets:
        self.logger.debug(f"received: {packet}")
        equipment = self.get_equipment(sender_address)
        if not equipment:
            # skip unknown sensor
            self.logger.info(f"unknown sender id {formatted_address}, telegram disregarded")
            return
        elif equipment.ignore:
            # skip ignored sensors
            self.logger.debug(f"ignored sensor: {formatted_address}")
            return

        # Handling EnOcean library decision to set learn to False by default.
        # Only 1BS and 4BS are correctly handled by the EnOcean library.
        # -> VLD EnOcean devices use UTE as learn mechanism
        # if equipment.rorg == RORG.VLD and packet.rorg != RORG.UTE:
        #     packet.learn = False
        # # -> RPS EnOcean devices only send normal data telegrams.
        # # Hence, learn can always be set to false
        # elif equipment.rorg == RORG.RPS:
        #     packet.learn = False
        # interpret packet, read properties and publish to MQTT
        self._parse_esp_packet(packet, equipment)

        # check for necessary reply
        if equipment.answer:
            self._reply_packet(packet, equipment)

    def _cleanup_mqtt(self):
        if self.publish_internal:
            self.mqtt_publish(f"{self.topic_prefix}{self.GATEWAY_STATUS_TOPIC}", "OFFLINE", retain=True)
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()

    # =============================================================================================
    # RUN LOOP
    # =============================================================================================
    def run(self):
        """the main loop with blocking enocean packet receive handler"""
        # start endless loop for listening
        while self.enocean.is_alive():
            # Request transmitter ID, if needed
            if self.controller_address is None:
                try:
                    self.enocean.init_adapter()
                    self.controller_address = self.enocean.base_id
                    self.logger.info(f"Base id {enocean.utils.to_hex_string(self.controller_address)}")
                    self.controller_info = self.enocean.controller_info_details
                    self.logger.info(f"Controller info: {self.controller_info}")
                except TimeoutError:
                    self.logger.error(f"Unable to retrieve adapter information in time")

            # Loop to empty the queue...
            try:
                # get next packet
                if platform.system() == 'Windows':
                    # only timeout on Windows for KeyboardInterrupt checking
                    packet = self.enocean.receive.get(block=True, timeout=1)
                else:
                    packet = self.enocean.receive.get(block=True)

                # check packet type
                if packet.packet_type == PacketTyoe.RADIO:
                    self._process_radio_packet(packet)
                elif packet.packet_type == PacketTyoe.RESPONSE:
                    response_code = ReturnCode(packet.data[0])
                    self.logger.info(f"got esp response packet: {response_code.name}")
                    if self.publish_response_status:
                        self.mqtt_publish(f"{self.topic_prefix}rep", response_code.name)
                else:
                    self.logger.info(f"got unsupported packet: type={packet.packet_type} {packet}")
                    continue
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                logging.debug("Exception: KeyboardInterrupt")
                break

        # Run finished, close MQTT client and stop Enocean thread
        logging.debug("Cleaning up")
        self.enocean.stop()
        self._cleanup_mqtt()
