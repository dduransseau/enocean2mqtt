import logging

import enocean.utils
from enocean.equipment import Equipment as EnoceanEquipment


class Equipment(EnoceanEquipment):
    logger = logging.getLogger("enocean.mqtt.equipment")

    def __init__(self, **kwargs):
        address = kwargs["address"]
        rorg = int(kwargs.get("rorg"))
        func = int(kwargs.get("func"))
        variant = int(kwargs.get("variant", 0)) or int(kwargs.get("type"))
        self.name = kwargs.get("name", str(address)) # Default set equipment address as name is none is set
        topic_prefix = kwargs.get("topic_prefix")
        if topic_prefix and self.name.startswith(topic_prefix):
            self.name = self.name.replace(topic_prefix, "")
        # self.logger.debug(f"Lookup profile for {rorg} {func} {type_}")
        super().__init__(address=address, rorg=rorg, func=func, variant=variant)
        self.publish_raw = self.get_config_boolean(kwargs, "publish_raw", default=False)
        self.publish_flat = self.get_config_boolean(
            kwargs, "publish_flat", default=False
        )
        self.publish_rssi = self.get_config_boolean(
            kwargs, "publish_rssi", default=True
        )
        self.use_key_shortcut = self.get_config_boolean(
            kwargs, "use_key_shortcut", default=False
        )
        self.retain = self.get_config_boolean(kwargs, "persistent", default=False)
        self.log_learn = self.get_config_boolean(kwargs, "log_learn", default=False)
        self.ignore = self.get_config_boolean(kwargs, "ignore", default=False)
        self.answer = kwargs.get("answer")
        self.command = kwargs.get("command", "CMD")
        self.channel = kwargs.get("channel")
        self.sender = kwargs.get("sender")
        self.direction = kwargs.get("direction")
        self.default_data = kwargs.get("default_data")
        self.first_seen = None
        self.last_seen = None
        self.rssi = None
        self.repeated = 0
        # self.data = dict()
        # Allow to specify a topic different from name to allow blank
        if topic := kwargs.get("topic"):
            self.topic = f"{topic_prefix}{topic}"
        else:
            self.topic = f"{topic_prefix}{self.name}"

    @staticmethod
    def get_config_boolean(c, key, default=False):
        if default:
            return False if c.get(key, True) in ("false", "False", "0", 0) else True
        else:
            return True if c.get(key, False) in ("true", "True", "1", 1) else False

    @property
    def address_label(self):
        return enocean.utils.to_hex_string(self.address)


    @property
    def definition(self):
        return dict(
            eep=self.eep_code,
            rorg=self.rorg,
            func=self.func,
            variant=self.variant,
            description=self.description,
            address=self.address_label,
            topic=self.topic,
            config=dict(
                publish_rssi=self.publish_rssi,
                retain=self.retain,
                ignore=self.ignore,
                command=self.command,
                sender=self.sender
            ),
        )
