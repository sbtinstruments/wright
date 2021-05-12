"""A module for interacting with the Seeed Studio Relay board for the Raspberry Pi."""
# =========================================================
# Seeed Studio Raspberry Pi Relay Board Library
#
# by John M. Wargo (www.johnwargo.com)
#
# Modified from the sample code on the Seeed Studio Wiki
# http://wiki.seeed.cc/Raspberry_Pi_Relay_Board_v1.0/
# =========================================================

# TODO: Rework this library to not use globals.
# pylint: disable=global-statement

from __future__ import print_function

import logging

import smbus2

_LOGGER = logging.getLogger(__name__)

# The number of relay ports on the relay board.
# This value should never change!
NUM_RELAY_PORTS = 4

# Change the following value if your Relay board uses a different I2C address.
DEVICE_ADDRESS = 0x20  # 7 bit address (will be left shifted to add the read write bit)

# Don't change the values, there's no need for that.
DEVICE_REG_MODE1 = 0x06
DEVICE_REG_DATA = 0xFF

bus = smbus2.SMBus(1)  # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)


def relay_on(relay_num: int) -> None:
    """Turn the specified relay (by relay #) on.

    Call this function to turn a single relay on.

    Args:
        relay_num (int): The relay number that you want turned on.
    """
    global DEVICE_ADDRESS
    global DEVICE_REG_DATA
    global DEVICE_REG_MODE1
    _raise_if_invalid_relay_num(relay_num)
    _LOGGER.debug("Turning relay %d ON", relay_num)
    DEVICE_REG_DATA &= ~(0x1 << (relay_num - 1))
    bus.write_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1, DEVICE_REG_DATA)


def relay_off(relay_num: int) -> None:
    """Turn the specified relay (by relay #) off.

    Call this function to turn a single relay off.

    Args:
        relay_num (int): The relay number that you want turned off.
    """
    global DEVICE_ADDRESS
    global DEVICE_REG_DATA
    global DEVICE_REG_MODE1
    _raise_if_invalid_relay_num(relay_num)
    _LOGGER.debug("Turning relay %d OFF", relay_num)
    DEVICE_REG_DATA |= 0x1 << (relay_num - 1)
    bus.write_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1, DEVICE_REG_DATA)


def relay_all_on() -> None:
    """Turn all of the relays on.

    Call this function to turn all of the relays on.
    """
    global DEVICE_ADDRESS
    global DEVICE_REG_DATA
    global DEVICE_REG_MODE1
    _LOGGER.debug("Turning all relays ON")
    DEVICE_REG_DATA &= ~(0xF << 0)
    bus.write_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1, DEVICE_REG_DATA)


def relay_all_off() -> None:
    """Turn all of the relays on.

    Call this function to turn all of the relays on.
    """
    global DEVICE_ADDRESS
    global DEVICE_REG_DATA
    global DEVICE_REG_MODE1
    _LOGGER.debug("Turning all relays OFF")
    DEVICE_REG_DATA |= 0xF << 0
    bus.write_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1, DEVICE_REG_DATA)


def relay_get_port_status(relay_num: int) -> bool:
    """Return the status of the specified relay (True for on, False for off).

    Call this function to retrieve the status of a specific relay.

    Args:
        relay_num (int): The relay number to query.
    """
    # determines whether the specified port is ON/OFF
    global DEVICE_REG_DATA
    _LOGGER.debug("Checking status of relay %d", relay_num)
    res = _relay_get_port_data(relay_num)
    if res <= 0:
        raise RuntimeError("Specified relay port is invalid")
    mask = 1 << (relay_num - 1)
    # return the specified bit status
    # return (DEVICE_REG_DATA & mask) != 0
    return (DEVICE_REG_DATA & mask) == 0


def _relay_get_port_data(relay_num: int) -> int:
    """Retrieve binary data from the relay board.

    Args:
        relay_num (int): The relay port to query.
    """
    # gets the current byte value stored in the relay board
    global DEVICE_REG_DATA
    _raise_if_invalid_relay_num(relay_num)
    # read the memory location
    DEVICE_REG_DATA = bus.read_byte_data(DEVICE_ADDRESS, DEVICE_REG_MODE1)
    # return the specified bit status
    return DEVICE_REG_DATA


def _raise_if_invalid_relay_num(relay_num: int) -> None:
    if not isinstance(relay_num, int):
        raise TypeError("The relay number must be an integer")
    if not 0 < relay_num <= NUM_RELAY_PORTS:
        raise ValueError(f"Invalid relay number: {relay_num}")
