from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, validator

from ..util import get_first_tty
from ._device_type import DeviceType
from ._validation import raise_if_bad_hostname
from .control import DeviceControl


class DeviceCommunication(BaseModel):
    """The host's means of communication with a device."""

    # We use this to, e.g., identify the device on the local network
    hostname: str
    # Terminal for the UART serial console
    tty: Path = Field(default_factory=get_first_tty)
    # We use this to identify the JTAG connection to the device
    jtag_usb_serial: Optional[str] = None

    # Note that we don't use `Field(default_factory=get_first_tty)`
    # because it doesn't allow us to get the default with `tty=None`.
    @validator("tty", pre=True, always=True)
    def _tty_default(  # pylint: disable=no-self-argument
        cls, value: Optional[Path]
    ) -> Path:
        if value is None:
            value = get_first_tty()
        return value

    class Config:  # pylint: disable=too-few-public-methods
        allow_mutation = False


class DeviceLink(BaseModel):
    """The host's connection to a device."""

    # Hardware controls to, e.g., turn the device on/off
    control: DeviceControl
    # Means of digital communication with the device
    communication: DeviceCommunication

    class Config:  # pylint: disable=too-few-public-methods
        allow_mutation = False


class DeviceDescription(BaseModel):
    """Identifies a specific device by its type and link to the host."""

    # Kind/class of the device
    device_type: DeviceType
    # Connection to the device by which we can, e.g., turn it on and send data.
    link: DeviceLink

    @validator("link")
    def _hostname_is_valid(  # pylint: disable=no-self-argument
        cls, value: DeviceLink, values: dict[str, Any]
    ) -> DeviceLink:
        if "device_type" in values:
            device_type = values["device_type"]
            assert isinstance(device_type, DeviceType)
            hostname = value.communication.hostname
            raise_if_bad_hostname(hostname, device_type)
        return value

    class Config:  # pylint: disable=too-few-public-methods
        allow_mutation = False

    @classmethod
    def from_raw_args(
        cls,
        *,
        device_type: DeviceType,
        hostname: str,
        tty: Optional[Path] = None,
        jtag_usb_serial: Optional[str] = None,
    ) -> DeviceDescription:
        """Return instance created from the given args.

        This is a convenience function that forwards the args to the
        constructors of the model hierarchy.
        """
        control = DeviceControl()
        communication = DeviceCommunication(
            hostname=hostname,
            tty=tty,
            jtag_serial=jtag_usb_serial,
        )
        link = DeviceLink(control=control, communication=communication)
        return cls(device_type=device_type, link=link)
