# Author: Damien Duransseau <damien@duransseau.net> based on Roman Morawek <roman.morawek@embyt.com> work
"""this class handles the enocean and mqtt interfaces"""

import logging
import queue
import json
import platform
import time

from enocean.controller.serialcontroller import SerialController
from enocean.protocol.packet import RadioPacket
from enocean.protocol.constants import (
    PacketType,
    FieldSetName,
)
from equipment import Equipment
from enocean.utils import combine_hex, to_hex_string, address_to_bytes_list
import paho.mqtt.client as mqtt


class Gateway:
    """the main working class providing the MQTT interface to the enocean packet classes"""

    mqtt_client = None
    enocean = None

    GATEWAY_TOPIC = "_gateway"
    TEACH_IN_TOPIC = f"{GATEWAY_TOPIC}/teach-in"
    ADAPTER_DETAILS_TOPIC = f"{GATEWAY_TOPIC}/adapter"
    GATEWAY_STATUS_TOPIC = f"{GATEWAY_TOPIC}/status"
    GATEWAY_EQUIPMENTS_TOPIC = f"{GATEWAY_TOPIC}/equipments"
    EQUIPMENT_REQUEST_TOPIC_SUFFIX = "/req"
    # Use underscore so that it is unique and doesn't match a potential future EnOcean EEP field.
    TIMESTAMP_MESSAGE_KEY = "_timestamp"
    RSSI_MESSAGE_KEY = "_rssi"
    CHANNEL_MESSAGE_KEY = "_channel"
    RORG_MESSAGE_KEY = "_rorg"

    logger = logging.getLogger("enocean.mqtt.gateway")

    def __init__(self, config):
        self.conf_manager = config
        self.conf = self.conf_manager.global_config
        self.publish_timestamp = self.conf.get("publish_timestamp", True)
        self.publish_raw = self.get_config_boolean("publish_raw")
        self.publish_internal = self.get_config_boolean("publish_internal")
        self.publish_response_status = self.get_config_boolean(
            "publish_response_status"
        )
        self.use_key_shortcut = self.conf.get("use_key_shortcut")
        if topic_prefix := self.conf.get("mqtt_prefix"):
            if not topic_prefix.endswith("/"):
                topic_prefix = f"{topic_prefix}/"
        else:
            topic_prefix = ""
        self.topic_prefix = topic_prefix
        self.logger.info(
            f"Init communicator with sensors: {self.conf_manager.equipments}, publish timestamp: {self.publish_timestamp}"
        )
        self.equipments = dict()
        # Define set() of detected address received by the gateway
        self.detected_equipments = set()
        # Set self.equipments based on sensors present in config_manager
        self.setup_devices_list()

        self.message_processed = 0
        self.message_sent = 0
        # check for mandatory configuration
        if "mqtt_host" not in self.conf or "enocean_port" not in self.conf:
            raise Exception("Mandatory configuration not found: mqtt_host and enocean_port")
        mqtt_port = int(self.conf["mqtt_port"]) if self.conf.get("mqtt_port") else 1883
        mqtt_keepalive = (
            int(self.conf["mqtt_keepalive"]) if self.conf.get("mqtt_keepalive") else 60
        )

        # setup enocean connection
        self.enocean = SerialController(
            self.conf["enocean_port"], teach_in=False, timestamp=self.publish_timestamp
        )
        self.enocean.start()
        # sender will be automatically determined
        self.controller_address = None
        self.controller_info = None

        # setup mqtt connection
        client_id = self.conf.get("mqtt_client_id", None)
        self.mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id
        )
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message
        if "mqtt_user" in self.conf:
            self.logger.info(f"authenticating: {self.conf['mqtt_user']}")
            self.mqtt_client.username_pw_set(
                self.conf["mqtt_user"], self.conf["mqtt_pwd"]
            )
        if self.get_config_boolean("mqtt_ssl"):
            self.logger.info("enabling SSL")
            ca_certs = (
                self.conf["mqtt_ssl_ca_certs"]
                if "mqtt_ssl_ca_certs" in self.conf
                else None
            )
            certfile = (
                self.conf["mqtt_ssl_certfile"]
                if "mqtt_ssl_certfile" in self.conf
                else None
            )
            keyfile = (
                self.conf["mqtt_ssl_keyfile"]
                if "mqtt_ssl_keyfile" in self.conf
                else None
            )
            self.mqtt_client.tls_set(
                ca_certs=ca_certs, certfile=certfile, keyfile=keyfile
            )
            if self.get_config_boolean("mqtt_ssl_insecure"):
                self.logger.warning("disabling SSL certificate verification")
                self.mqtt_client.tls_insecure_set(True)
        if self.get_config_boolean("mqtt_debug"):
            self.mqtt_client.enable_logger()
        self.log_packets = self.get_config_boolean("log_packets")
        self.logger.debug(
            f"connecting to host {self.conf['mqtt_host']}, port {mqtt_port}, keepalive {mqtt_keepalive}"
        )
        self.mqtt_qos = int(self.conf["mqtt_qos"]) if self.conf.get("mqtt_qos") else 0
        self.mqtt_client.connect_async(
            self.conf["mqtt_host"], port=mqtt_port, keepalive=mqtt_keepalive
        )
        self.mqtt_client.loop_start()

    def __del__(self):
        if self.enocean is not None and self.enocean.is_alive():
            self.enocean.stop()

    def get_config_boolean(self, key):
        return (
            True
            if self.conf.get(key, False) in ("true", "True", "1", 1, True)
            else False
        )

    def get_equipment_by_topic(self, topic):
        for equipment in self.equipments.values():
            if f"{equipment.topic}/" in topic:
                return equipment

    def get_equipment(self, id):
        """Try to get the equipment based on id (can be address or name)"""
        if equipment := self.equipments.get(id):
            return equipment
        # if equipment not found by id, lookup by name
        for equipment in self.equipments.values():
            if id == equipment.name:
                return equipment
        self.logger.debug(f"Unable to find equipment with key {id:x}")

    def setup_devices_list(self, force=False):
        """ Initialise the list of known device
        force: force to load the config file from disk in case device config as been added
        """
        if force:
            self.conf_manager.load_config_file(omit_global=True)
        for s in self.conf_manager.equipments:
            address = s.get("address")
            try:
                s["topic_prefix"] = self.topic_prefix
                equipment = Equipment(**s)
                self.equipments[address] = equipment
            except NotImplementedError:
                self.logger.warning(f"Unable to setup device {address}")

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

    def mqtt_publish(self, topic, payload, retain=False, qos=1):
        # Helper that publish mqtt message using global config and handling dict as json
        qos = qos or self.mqtt_qos
        if isinstance(payload, dict) or isinstance(payload, list):
            payload = json.dumps(payload)
        msg_info = self.mqtt_client.publish(topic, payload, retain=retain, qos=qos)
        self.message_processed = msg_info.mid
        self.message_sent += 1

    def mqtt_subscribe(self, topic, qos=1):
        result, mid = self.mqtt_client.subscribe(topic, qos)
        self.message_processed = mid

    def _on_connect(self, mqtt_client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.logger.info("successfully connected to MQTT broker.")
            self.logger.debug(f"subscribe to root req topic: {self.topic_prefix}req")
            self.mqtt_subscribe(f"{self.topic_prefix}req")
            self.mqtt_subscribe(f"{self.topic_prefix}learn")
            self.mqtt_subscribe(f"{self.topic_prefix}reload")
            if self.publish_internal:
                self.mqtt_publish(
                    f"{self.topic_prefix}{self.GATEWAY_STATUS_TOPIC}",
                    "ONLINE",
                    retain=True,
                )
                # listen to enocean send requests
                for equipment in self.equipments.values():
                    # logging.debug("MQTT subscribing: %s", cur_sensor['name']+'/req/#')
                    self.mqtt_subscribe(equipment.topic + self.EQUIPMENT_REQUEST_TOPIC_SUFFIX)
                self.mqtt_publish(
                    f"{self.topic_prefix}{self.GATEWAY_EQUIPMENTS_TOPIC}",
                    self.equipments_definition_list,
                    retain=True,
                )
                self._publish_gateway_adapter_details()
        else:
            self.logger.error(f"error connecting to MQTT broker: {reason_code}")

    def _publish_gateway_adapter_details(self):
        # Wait that enocean communicator is initialized before publishing teach in mode
        self.enocean.init_adapter()
        self.controller_address = self.enocean.base_id
        self.controller_info = self.enocean.controller_info_details
        # for i in range(10):
        #     if self.controller_address is None:
        #         try:
        #             self.enocean.init_adapter()
        #             self.controller_address = self.enocean.base_id
        #             self.controller_info = self.enocean.controller_info_details
        #         except TimeoutError:
        #             self.logger.error("Unable to retrieve adapter information in time")
        #     elif self.controller_address and self.controller_info:
        #         break
        #     time.sleep(0.01)
        try:
            teach_in = "ON" if self.enocean.teach_in else "OFF"
            self.mqtt_publish(
                f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", teach_in, retain=True
            )
            payload = self.controller_info
            payload["address"] = to_hex_string(self.controller_address)  # Set it back
            self.mqtt_publish(
                f"{self.topic_prefix}{self.ADAPTER_DETAILS_TOPIC}", payload, retain=True
            )
        except Exception:
            self.logger.exception(Exception)

    def _on_disconnect(self, mqtt_client, userdata, flags, reason_code, properties):
        # callback for when the client disconnects from the MQTT server.
        if reason_code == 0:
            self.logger.info("successfully disconnected from MQTT broker")
        else:
            self.logger.warning(
                f"unexpectedly disconnected from MQTT broker: {reason_code}"
            )

    def _on_mqtt_message(self, mqtt_client, userdata, msg):
        # search for sensor
        self.logger.info("received MQTT message: %s", msg.topic)
        if msg.topic == f"{self.topic_prefix}learn":
            self.handle_learn_activation_request(msg)
        elif msg.topic == f"{self.topic_prefix}reload":
            self.handle_reload_equipments_request()
        else:
            # Get how to handle MQTT message
            try:
                mqtt_payload = json.loads(msg.payload)
                try:
                    self._mqtt_message_json(msg.topic, mqtt_payload)
                except Exception as e:
                    self.logger.warning(
                        f"unexpected or erroneous MQTT message: {msg.topic}: {msg.payload}"
                    )
                    self.logger.exception(e)
            except json.decoder.JSONDecodeError:
                self.logger.warning(
                    f"Received message payload is not json type: {msg.payload}"
                )
            except Exception:
                self.logger.error(f"unable to send {msg}")
                self.logger.exception(Exception)

    def handle_learn_activation_request(self, msg):
        command = msg.payload.decode("utf-8").upper()
        if command == "ON":
            self.enocean.teach_in = True
            self.logger.info("gateway teach in mode enabled")
        elif command == "OFF":
            self.enocean.teach_in = False
            self.logger.info("gateway teach in mode disabled ")
        else:
            self.logger.warning(f"not supported command: {command} for learn")
            return
        if self.publish_internal:
            self.mqtt_publish(
                f"{self.topic_prefix}{self.TEACH_IN_TOPIC}", command, retain=True
            )

    def handle_reload_equipments_request(self):
        self.logger.info("Reload equipments list")
        self.setup_devices_list(force=True)
        self.mqtt_publish(
            f"{self.topic_prefix}{self.GATEWAY_EQUIPMENTS_TOPIC}",
            self.equipments_definition_list,
            retain=True,
        )
        self.logger.debug(f"New equipments list {self.equipments}")

    # =============================================================================================
    # MQTT TO ENOCEAN
    # =============================================================================================

    def _mqtt_message_json(self, mqtt_topic, mqtt_json_payload):
        # Handle received PUBLISH message from the MQTT server as a JSON payload.
        # TODO: Define a elegant way to parse equipment topic and lookup on dict
        equipment = self.get_equipment_by_topic(mqtt_topic)
        # If the equipment is not specified in topic path, check if specified in payload
        if not equipment:
            try:
                equipment_id = mqtt_json_payload["equipment"]
                equipment = self.get_equipment(equipment_id)
                del mqtt_json_payload[
                    "equipment"
                ]  # Remove key to avoid to have it during for loop
            except KeyError:
                self.logger.warning(
                    f"unable to get equipment topic={mqtt_topic} payload={mqtt_json_payload}"
                )
                return None
        self.logger.debug(f"found {equipment} for message in topic {mqtt_topic}")
        # JSON payload shall be sent to '/req' topic
        # if mqtt_topic.endswith(self.EQUIPMENT_REQUEST_TOPIC_SUFFIX): # Seems useless since equipment subscription already filter this
        self._handle_mqtt_message(equipment, mqtt_json_payload)
        # try:
        #     # JSON payload shall be sent to '/req' topic
        #     if mqtt_topic.endswith("/req"):
        #         self._handle_mqtt_message(equipment, mqtt_json_payload)
        # except AttributeError:
        #     self.logger.warning(
        #         f"unable to handle message topic={mqtt_topic} payload={mqtt_json_payload}"
        #     )

    def _handle_mqtt_message(self, equipment, payload):
        # Send received MQTT message to EnOcean.
        self.logger.debug(f"Message {payload} to send to {equipment.address}")
        # Check MQTT message has valid data
        if not payload:
            self.logger.warning("no data to send from MQTT message!")
            return
        command_id = None
        command_shortcut = (
            equipment.command
        )  # Get the command shortcut used by the device (commonly "CMD")
        if command_shortcut:
            # Check MQTT message sets the command field and set the command id
            if command_id := payload.get(command_shortcut):
                self.logger.debug(
                    f"retrieved command id from MQTT message: {hex(command_id)}"
                )
            else:
                self.logger.warning(
                    f"command field {command_shortcut} must be set in MQTT message!"
                )
                return
        self._send_packet_to_esp(equipment, data=payload, command=command_id)
        self.logger.debug("Clearing data buffer.")

    # =============================================================================================
    # ENOCEAN TO MQTT
    # =============================================================================================

    def _publish_mqtt_json(self, equipment, mqtt_json, channel=None):
        """Publish decoded packet content to MQTT"""
        # Retain the to-be-published message ?
        retain = equipment.retain
        # Determine MQTT topic
        topic = equipment.topic

        # Is grouping enabled on this sensor
        # if self.CHANNEL_MESSAGE_KEY in mqtt_json.keys():
        #     topic += f"/{mqtt_json[self.CHANNEL_MESSAGE_KEY]}"
            # del mqtt_json[self.CHANNEL_MESSAGE_KEY]
        if channel:
            topic += f"/{channel}"

        # Publish packet data to MQTT
        self.logger.debug(f"{topic}: Sent MQTT: {mqtt_json}")
        self.mqtt_publish(topic, mqtt_json, retain=retain)
        # if equipment.publish_flat:
        #     for prop_name, value in mqtt_json.items():
        #         prop_name = prop_name.replace(
        #             "/", ""
        #         )  # Avoid sub topic if property has / ex: "I/O"
        #         if prop_name.endswith("|unit"):
        #             val_name = prop_name.split("|")[0]
        #             unit = value
        #             self.mqtt_publish(f"{topic}/{val_name}/$unit", unit, retain=retain)
        #         else:
        #             self.mqtt_publish(f"{topic}/{prop_name}", value, retain=retain)

    def _publish_mqtt_flat(self, equipment, fields_list, channel=None):
        # retain = equipment.retain
        retain = True
        base_topic = equipment.topic
        if channel:
            base_topic += f"/{channel}"
        for field in fields_list:
            self.mqtt_publish(f"{base_topic}/{field[FieldSetName.SHORTCUT]}", field[FieldSetName.VALUE], retain=retain)
            self.mqtt_publish(f"{base_topic}/{field[FieldSetName.SHORTCUT]}/$name", field[FieldSetName.DESCRIPTION], retain=retain)
            if field.get(FieldSetName.UNIT):
                self.mqtt_publish(f"{base_topic}/{field[FieldSetName.SHORTCUT]}/$unit", field[FieldSetName.UNIT],
                                  retain=retain)

    def _process_erp_packet(self, packet, equipment):
        """interpret radio packet, read properties and publish to MQTT"""
        if not packet.learn or equipment.log_learn:
            # Handling received data packet
            self.logger.debug(f"handle radio packet for sensor {equipment}")
            # Parse message based on fields definition (profile)
            radio_message = packet.parse_erp_message(equipment.profile, direction=equipment.direction)
            if not radio_message:
                self.logger.warning(
                    f"message not interpretable: {equipment.name} {packet}"
                )
            else:
                channel = None
                message_payload = self.format_enocean_message(radio_message, equipment)
                if self.CHANNEL_MESSAGE_KEY in message_payload.keys():
                    channel = message_payload[self.CHANNEL_MESSAGE_KEY]
                # Store receive date
                if self.publish_timestamp:
                    message_payload[self.TIMESTAMP_MESSAGE_KEY] = int(packet.received)
                if equipment.publish_rssi:
                    # Store RSSI
                    try:
                        message_payload[self.RSSI_MESSAGE_KEY] = packet.dBm
                    except AttributeError:
                        self.logger.warning(
                            f"Unable to set RSSI value in packet {packet}"
                        )
                message_payload[self.RORG_MESSAGE_KEY] = packet.rorg
                self.logger.debug(f"Publish message {message_payload}")
                self._publish_mqtt_json(equipment, message_payload, channel=channel)
                if equipment.publish_flat:
                    self._publish_mqtt_flat(equipment, radio_message, channel=channel)
        elif packet.learn and not self.enocean.teach_in:
            self.logger.info("Received teach-in packet but learn is not enabled")
        else:
            # learn request received
            self.logger.info("learn request not emitted to mqtt")

    def format_enocean_message(self, parsed_message, equipment):
        """
        parsed_message: list of EEP dict() field
        equipment: equipment linked that sent message

        return: dict() with formatted fields and units
        """
        message_payload = dict()
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
            if (
                isinstance(prop[FieldSetName.VALUE], str)
                and "not supported" in prop[FieldSetName.VALUE]
            ):
                continue
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

    def _reply_packet(self, packet, equipment):
        """send enocean message as a reply to an incoming message"""
        # prepare addresses
        # destination = packet.sender
        self._send_packet_to_esp(
            equipment,
            data=equipment.answer,
            command=None,
            negate_direction=True,
            learn_data=packet.data if packet.learn else None,
        )

    def _send_packet_to_esp(
        self,
        equipment,
        data=None,
        command=None,
        negate_direction=False,
        learn_data=None,
    ):
        """triggers sending of an enocean packet"""
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
        sender = (
            address_to_bytes_list(equipment.sender)
            if equipment.sender
            else self.controller_address
        )

        try:
            packet = RadioPacket.create_message(
                equipment,
                direction=direction,
                command=command,
                sender=sender,
                learn=is_learn,
            )
            self.logger.debug(f"Packet built: {packet.data}")
        except (ValueError, NotImplemented) as err:
            self.logger.error(f"cannot create RF packet: {err}")
            return

        # assemble data based on packet type (learn / data)
        if is_learn:
            # learn request received
            # copy EEP and manufacturer ID
            packet.data[1:5] = learn_data[1:5]
            # update flags to acknowledge learn request
            packet.data[4] = 0xF0
        else:
            # data packet received
            # start with default data
            # Initialize packet with default_data if specified
            if equipment.default_data:
                packet.data[1:5] = [
                    (equipment.default_data >> i * 8) & 0xFF for i in reversed(range(4))
                ]
            # do we have specific data to send?
            if data:
                # override with specific data settings
                self.logger.debug(f"packet with message {packet.message}")
                packet = packet.build_message(data)
            else:
                # what to do if we have no data to send yet?
                self.logger.warning(f"sending only default data as answer to {equipment.name}")
        self.enocean.send(packet)

    def add_equipments(self, publish=True):
        # Allow to add equipment live without config file if teach-in packet received with eep
        ignore = False if self.enocean.teach_in else True
        for i in range(len(self.enocean.learned_equipment)):
            new_equipment = self.enocean.learned_equipment.pop()
            equipment = Equipment(address=new_equipment.address, rorg=new_equipment.rorg, func=new_equipment.func, type=new_equipment.type,
                                  topic_prefix=self.topic_prefix, ignore=ignore)
            self.equipments[new_equipment.address] = equipment
            self.mqtt_subscribe(equipment.topic + "/req")
            self.conf_manager.save_discovered_equipment(equipment)
        if publish:
            self.mqtt_publish(
                f"{self.topic_prefix}{self.GATEWAY_EQUIPMENTS_TOPIC}",
                self.equipments_definition_list,
                retain=True,
            )

    def _handle_erp_packet(self, packet):
        # first, look whether we have this sensor configured
        sender_address = combine_hex(packet.sender)
        formatted_address = to_hex_string(packet.sender)
        self.logger.debug(f"process radio for address {formatted_address}")
        if sender_address not in self.detected_equipments:
            self.detected_equipments.add(sender_address)
            self.logger.info(f"Detected new equipment with address {formatted_address}")
            # self.mqtt_publish(f"{self.topic_prefix}gateway/detected_equipments", list(self.detected_equipments))
        self.logger.debug(f"received: {packet}")
        # Check if new device has been detected and add it to known equipment
        if self.enocean.learned_equipment:
            self.add_equipments()

        equipment = self.get_equipment(sender_address)
        if not equipment:
            # skip unknown sensor
            self.logger.debug(
                f"unknown sender id {formatted_address}, telegram disregarded"
            )
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
        self._process_erp_packet(packet, equipment)

        # check for necessary reply
        if equipment.answer:
            self._reply_packet(packet, equipment)

    def _cleanup_mqtt(self):
        if self.publish_internal:
            self.mqtt_publish(
                f"{self.topic_prefix}{self.GATEWAY_STATUS_TOPIC}",
                "OFFLINE",
                retain=True,
            )
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()

    # =============================================================================================
    # RUN LOOP
    # =============================================================================================
    def run(self):
        """the main loop with blocking enocean packet receive handler"""
        # start endless loop for listening
        while self.enocean.is_alive():
            # Loop to empty the queue...
            try:
                # get next packet
                if platform.system() == "Windows":
                    # only timeout on Windows for KeyboardInterrupt checking
                    packet = self.enocean.receive.get(block=True, timeout=1)
                else:
                    packet = self.enocean.receive.get(block=True)
                # check packet type
                if packet.packet_type == PacketType.RADIO_ERP1:
                    self._handle_erp_packet(packet)
                elif packet.packet_type == PacketType.RESPONSE:
                    self.logger.debug(f"got esp response packet: {packet.return_code.name}")
                    if self.publish_response_status:
                        self.mqtt_publish(f"{self.topic_prefix}rep", packet.return_code.name)
                elif packet.packet_type == PacketType.EVENT:
                    self.logger.warning(f"Received EVENT packet {packet}")
                else:
                    self.logger.info(
                        f"got unsupported packet: type={packet.packet_type} {packet}"
                    )
                    continue
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                logging.debug("Exception: KeyboardInterrupt")
                break
        # Run finished, close MQTT client and stop Enocean thread
        self.mqtt_publish(
            f"{self.topic_prefix}{self.GATEWAY_STATUS_TOPIC}",
            "OFFLINE",
            retain=True,
        )
        self.logger.info(
            f"Close the enocean controller, get {self.enocean.crc_errors} crc errors during run"
        )
        self.logger.debug("Cleaning up")
        self.enocean.stop()
        self._cleanup_mqtt()
