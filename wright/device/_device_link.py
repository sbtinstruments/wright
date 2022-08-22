from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, validator

from ..model import FrozenModel
from ..util import get_first_tty
from .control import DeviceControl


class DeviceCommunication(FrozenModel):
    """The host's means of communication with a device."""

    # We use this to, e.g., identify the device on the local network
    hostname: str
    # Terminal for the UART serial command line
    tty: Path = Field(default_factory=get_first_tty)
    # We use the `jtag_usb_*` fields to identify the JTAG connection to the device.
    # You can either specify:
    #
    #  1. The `jtag_usb_serial` field
    #  2. Both the `jtag_usb_hub_location` and `jtag_usb_hub_port` fields.
    #
    # If you mix (1) and (2), we use (2) if we need to power cycle the USB connection.
    # E.g., to recover the JTAG USB cable from a bad state.
    #
    # (1) is high-level and assumes that the USB connection is in a good state
    # so that the device can report it's own ID. You can plug the USB device itself
    # into any USB hub and any port in said hub.
    # (2) is low-level and works even if the USB connection is in a bad state.
    # You have to plug the device into a specific hub
    # and a specific port in said hub.
    jtag_usb_serial: Optional[str] = None
    jtag_usb_hub_location: Optional[str] = None
    jtag_usb_hub_port: Optional[int] = None
    # Open On-Chip Debugger (OCD) port
    ocd_tcl_port: Optional[int] = None

    # Note that we don't use `Field(default_factory=get_first_tty)`
    # because it doesn't allow us to get the default with `tty=None`.
    @validator("tty", pre=True, always=True)
    def _tty_default(  # pylint: disable=no-self-argument
        cls, value: Optional[Path]
    ) -> Path:
        if value is None:
            value = get_first_tty()
        return value


class DeviceLink(FrozenModel):
    """The host's connection to a device."""

    # Hardware controls to, e.g., turn the device on/off
    control: DeviceControl
    # Means of digital communication with the device
    communication: DeviceCommunication
