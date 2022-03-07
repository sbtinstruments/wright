from __future__ import annotations

from pathlib import Path
from re import compile, match
from typing import Any, Optional

from pydantic import validator

from ..model import FrozenModel
from ._device_link import DeviceCommunication, DeviceLink
from ._device_metadata import DeviceMetadata
from ._device_type import DeviceType
from ._validation import raise_if_bad_hostname
from .control import DeviceControl
from .control.boot_mode import GpioBootModeControl
from .control.power import RelayPowerControl

_DEVICE_VERSION_REGEX = compile(r"[0-9][A-Za-z0-9-_.]+")


class DeviceDescription(FrozenModel):
    """Identifies a specific device by its type and link to the host."""

    # Kind/class of the device
    device_type: DeviceType
    # Version of the device
    device_version: str
    # Connection to the device by which we can, e.g., turn it on and send data.
    link: DeviceLink
    # Metadata such as the device condition, firmware version, etc.
    metadata: DeviceMetadata = DeviceMetadata()

    @validator("device_version")
    def _version_is_valid(cls, value: str) -> str:  # pylint: disable=no-self-argument
        if _DEVICE_VERSION_REGEX.fullmatch(value) is None:
            raise ValueError("Invalid version string")
        return value

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

    @classmethod
    def from_raw_args(
        cls,
        *,
        device_type: DeviceType,
        device_version: str,
        hostname: str,
        tty: Optional[Path] = None,
        jtag_usb_serial: Optional[str] = None,
        power_relay: Optional[int] = None,
        boot_mode_gpio: Optional[int] = None,
    ) -> DeviceDescription:
        """Return instance created from the given args.

        This is a convenience function that forwards the args to the
        constructors of the model hierarchy.
        """
        control_args: dict[str, Any] = {}
        if power_relay is not None:
            control_args["power"] = RelayPowerControl(relay_id=power_relay)
        if boot_mode_gpio is not None:
            control_args["boot_mode"] = GpioBootModeControl(gpio_id=boot_mode_gpio)
        control = DeviceControl(**control_args)
        communication = DeviceCommunication(
            hostname=hostname,
            tty=tty,
            jtag_usb_serial=jtag_usb_serial,
        )
        link = DeviceLink(control=control, communication=communication)
        return cls(
            device_type=device_type,
            device_version=device_version,
            link=link,
        )
