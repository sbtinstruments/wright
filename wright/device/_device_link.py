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
    # We use this to identify the JTAG connection to the device
    jtag_usb_serial: Optional[str] = None
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
