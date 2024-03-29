#!/usr/bin/env python3
# Author: Damien Duransseau <damien@duransseau.net> based on Roman Morawek <roman.morawek@embyt.com>
"""this is the main entry point, which sets up the Communicator class"""
import logging
import sys
import copy
import argparse
from pathlib import Path
from configparser import ConfigParser

from communicator import Communicator


conf = {
    'debug': False,
    'config': ['/etc/gateway.conf', '../gateway.conf', '../equipments.conf'],
    'logfile': '../gateway.log'
}


class ConfigManager:

    def __init__(self, conf):
        self._conf = conf
        self.logging_level = logging.DEBUG if self._conf.get('debug') else logging.INFO
        self.logging_file = self._conf.get('logfile')
        self.config_files = self._conf.get('config', [])
        self.sensors = []
        self.global_config = {}

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
        self.sensors = []
        if not omit_global: # Empty the global config only if it's not omitted
            self.global_config = {}
        logger = logging.getLogger("enocean.mqtt.config")
        config_parser = ConfigParser(inline_comment_prefixes=('#', ';'), interpolation=None)
        for conf_file in self.config_files:
            if not Path(conf_file).is_file():
                logger.warning("Config file %s does not exist, skipping", conf_file)
                continue
            logger.info("Loading config file %s", conf_file)
            if not config_parser.read(conf_file):
                logger.error("Cannot read config file: %s", conf_file)
                sys.exit(1)
            for section in config_parser.sections():
                if section == 'CONFIG':
                    if omit_global:
                        continue
                    # general configuration is part of CONFIG section
                    for key in config_parser[section]:
                        self.global_config[key] = self.config_parse_value(config_parser[section][key])
                else:
                    mqtt_prefix = self.global_config['mqtt_prefix'] \
                        if 'mqtt_prefix' in self.global_config else "enocean/"
                    new_sens = {'name': mqtt_prefix + section}
                    for key in config_parser[section]:
                        try:
                            # new_sens[key] = config_parser[section][key]
                            if key in ('address', 'rorg', "func", "type"):
                                new_sens[key] = int(config_parser[section][key], 16)
                            else:
                                new_sens[key] = config_parser[section][key]
                        except KeyError:
                            new_sens[key] = None
                    self.sensors.append(new_sens)
                    logger.debug("Created sensor: %s", new_sens)
        if not omit_global:
            logging_global_config = copy.deepcopy(self.global_config)
            if "mqtt_pwd" in logging_global_config:
                logging_global_config["mqtt_pwd"] = "*****"
            logger.debug("Global config: %s", logging_global_config)


def parse_args():
    """ Parse command line arguments. """
    parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    parser.add_argument('--debug', help='enable console debugging', action='store_true')
    parser.add_argument('--logfile', help='set log file location')
    parser.add_argument('config', help='specify config file[s]', nargs='*')
    # parser.add_argument('--version', help='show application version',
    #     action='version', version='%(prog)s ' + VERSION)
    args = vars(parser.parse_args())
    # logging.info('Read arguments: ' + str(args))
    return args


def setup_logging(log_filename='', log_level=logging.INFO):
    """initialize python logging infrastructure"""
    # create formatter
    log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')

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
    # logging.getLogger().setLevel(logging.DEBUG)
    # Parse command line arguments
    conf.update(parse_args())
    config_manager= ConfigManager(conf)
    # setup logger
    setup_logging(config_manager.logging_file, config_manager.logging_level)
    # load config file
    config_manager.load_config_file()

    # start working
    com = Communicator(config_manager)
    try:
        com.run()
    except Exception as e:
        logging.exception(e)


# check for execution
if __name__ == "__main__":
    main()
