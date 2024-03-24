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


def config_parse_value(v):
    if v.isdigit():
        return int(v)
    elif v.lower() in ("true", "yes"):
        return True
    elif v.lower() in ("false", "no"):
        return False
    return v


def load_config_file(config_files):
    """load sensor and general configuration from given config files"""
    # extract sensor configuration
    sensors = []
    global_config = {}
    equipments_file = None

    logger = logging.getLogger("enocean.mqtt.config")
    config_parser = ConfigParser(inline_comment_prefixes=('#', ';'), interpolation=None)
    for conf_file in config_files:

        if not Path(conf_file).is_file():
            logger.warning("Config file %s does not exist, skipping", conf_file)
            continue
        logger.info("Loading config file %s", conf_file)
        if not config_parser.read(conf_file):
            logger.error("Cannot read config file: %s", conf_file)
            sys.exit(1)

        for section in config_parser.sections():
            if section == 'CONFIG':
                # general configuration is part of CONFIG section
                for key in config_parser[section]:
                    global_config[key] = config_parse_value(config_parser[section][key])
            else:
                if not equipments_file:
                    equipments_file = conf_file
                elif conf_file != equipments_file:
                    logger.warning("There is multiple files that host equipments config, only one can be reload")
                mqtt_prefix = global_config['mqtt_prefix'] \
                    if 'mqtt_prefix' in global_config else "enocean/"
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
                sensors.append(new_sens)
                logger.debug("Created sensor: %s", new_sens)

    logging_global_config = copy.deepcopy(global_config)
    if "mqtt_pwd" in logging_global_config:
        logging_global_config["mqtt_pwd"] = "*****"
    logger.debug("Global config: %s", logging_global_config)

    return sensors, global_config


def setup_logging(log_filename='', log_level=logging.INFO):
    """initialize python logging infrastructure"""
    # create formatter
    log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s') # %(asctime)s - %(name)s - %(levelname)s - %(message)s

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

    # setup logger
    setup_logging(conf['logfile'], logging.DEBUG if conf['debug'] else logging.INFO)
    # load config file
    sensors, global_config = load_config_file(conf['config'])
    conf.update(global_config)

    # start working
    com = Communicator(conf, sensors)
    try:
        com.run()
    except Exception as e:
        logging.exception(e)


# check for execution
if __name__ == "__main__":
    main()
