#!/usr/bin/env python3
# Author: Damien Duransseau <damien@duransseau.net>
"""this is the main entry point, which sets up the Communicator class"""
import logging
import os
import sys
import tempfile
import copy
import argparse
from pathlib import Path
from configparser import ConfigParser, DuplicateSectionError

from gateway import Gateway

DISCOVERED_EQUIPMENTS_FILE = "./discovered.conf"

conf = {
    "debug": False,
    "config": ["/etc/gateway.conf", "./gateway.conf", "./equipments.conf"],
    "logfile": "./gateway.log",
}


class ConfigManager:
    def __init__(self, conf):
        self._conf = conf
        self.logging_level = logging.DEBUG if self._conf.get("debug") else logging.INFO
        self.logging_file = self._conf.get("logfile")
        self.config_files = self._conf.get("config", [])
        self.equipments = list()
        self.global_config = {}
        self._discovered_config = None

    @staticmethod
    def config_parse_value(v):
        if v.isdigit():
            return int(v)
        elif v.lower() in ("true", "yes"):
            return True
        elif v.lower() in ("false", "no"):
            return False
        return v

    def load_config_file(self, omit_global=False):
        """load sensor and general configuration from given config files"""
        # extract sensor configuration
        self.equipments = list()
        if not omit_global:  # Empty the global config only if it's not omitted
            self.global_config = {}
        logger = logging.getLogger("enocean.mqtt.config")
        config_parser = ConfigParser(
            inline_comment_prefixes=("#", ";"), interpolation=None
        )
        for conf_file in self.config_files:
            if not Path(conf_file).is_file():
                logger.warning("Config file %s does not exist, skipping", conf_file)
                continue
            logger.info("Loading config file %s", conf_file)
            if not config_parser.read(conf_file):
                logger.error("Cannot read config file: %s", conf_file)
                sys.exit(1)
            elif conf_file == DISCOVERED_EQUIPMENTS_FILE:
                self._discovered_config = config_parser
            for section in config_parser.sections():
                if section == "CONFIG":
                    if omit_global:
                        continue
                    # general configuration is part of CONFIG section
                    for key in config_parser[section]:
                        self.global_config[key] = self.config_parse_value(
                            config_parser[section][key]
                        )
                else:
                    mqtt_prefix = (
                        self.global_config["mqtt_prefix"]
                        if "mqtt_prefix" in self.global_config
                        else "enocean/"
                    )
                    equipment_config = {"name": section}
                    # equipment_config = {"name": mqtt_prefix + section}
                    for key in config_parser[section]:
                        try:
                            # equipment_config[key] = config_parser[section][key]
                            if key in ("address", "rorg", "func", "type"):
                                equipment_config[key] = int(config_parser[section][key], 16)
                            else:
                                equipment_config[key] = config_parser[section][key]
                        except KeyError:
                            equipment_config[key] = None
                        except ValueError:
                            logger.error(
                                f"Invalid value for {key} in section {section}: {config_parser[section][key]}"
                            )
                    self.equipments.append(equipment_config)
                    logger.debug("Created sensor: %s", equipment_config)
        if not omit_global:
            logging_global_config = copy.deepcopy(self.global_config)
            if "mqtt_pwd" in logging_global_config:
                logging_global_config["mqtt_pwd"] = "*****"
            logger.debug("Global config: %s", logging_global_config)
        # self.save_equipment()

    def save_discovered_equipment(self, equipment):
        if self._discovered_config is None:
            self._discovered_config = ConfigParser(
                inline_comment_prefixes=("#", ";"), interpolation=None
            )
            self._discovered_config.read(DISCOVERED_EQUIPMENTS_FILE)
        config = self._discovered_config
        address = str(equipment.address)

        try:
            config.add_section(address)
        except DuplicateSectionError:
            pass

        config.set(address, "address", f"{hex(equipment.address)}")
        config.set(address, "rorg", f"{hex(equipment.rorg)}")
        config.set(address, "func", f"{hex(equipment.func)}")
        config.set(address, "type", f"{hex(equipment.variant)}")

        # Create a temporary file in the same directory as the target file
        target = Path(DISCOVERED_EQUIPMENTS_FILE)
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent or ".", prefix=target.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wt", encoding="utf-8") as tmp_file:
                config.write(tmp_file)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, target)
        except Exception:
            os.unlink(tmp_path)
            raise


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument("--debug", help="enable console debugging", action="store_true")
    parser.add_argument("--logfile", help="set log file location")
    parser.add_argument("config", help="specify config file[s]", nargs="*")
    # parser.add_argument('--version', help='show application version',
    #     action='version', version='%(prog)s ' + VERSION)
    args = vars(parser.parse_args())
    # logging.info('Read arguments: ' + str(args))
    return args


def setup_logging(log_filename="", log_level=logging.INFO):
    """initialize python logging infrastructure"""
    # create formatter
    log_formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")

    # set root logger to lowest log level
    logging.getLogger().setLevel(log_level)

    # create console and log file handlers and the formatter to the handlers
    log_console = logging.StreamHandler(sys.stdout)
    log_console.setFormatter(log_formatter)
    log_console.setLevel(log_level)
    logging.getLogger().addHandler(log_console)
    if log_filename:
        log_file = logging.FileHandler(log_filename)
        log_file.setLevel(log_level)
        log_file.setFormatter(log_formatter)
        logging.getLogger().addHandler(log_file)
        logging.info("Logging to file: %s", log_filename)


def main():
    """entry point if called as an executable"""
    try:
        # logging.getLogger().setLevel(logging.DEBUG)
        # Parse command line arguments
        conf.update(parse_args())
        config_manager = ConfigManager(conf)
        # setup logger
        setup_logging(config_manager.logging_file, config_manager.logging_level)
        # load config file
        config_manager.load_config_file()

        # start working
        com = Gateway(config_manager)
        com.run()
    except RuntimeError:
        logging.critical("Unable to connect to EnOcean controller, exit")
        sys.exit(1)
    except Exception as e:
        logging.exception(e)
        sys.exit(1)


# check for execution
if __name__ == "__main__":
    main()
