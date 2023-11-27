from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import constr, root_validator, Field

from ..model import FrozenModel
from ._device_link import DeviceCommunication, DeviceLink
from ._device_metadata import DeviceMetadata
from ._device_type import DeviceType
from .control import DeviceControl
from .control.boot_mode import GpioBootModeControl
from .control.power import RelayPowerControl
from .models import HardwareIdentificationGroup


# These item numbers come directly from SBT's ERP system
#  (Microsoft Dynamics 365 Business Central)
_DEVICE_PCB_ITEM_NUMBER: dict[DeviceType, tuple(int)] = {
    DeviceType.BACTOBOX: (10196,),
    DeviceType.ZEUS: (20045,),
}

# Default hostname placeholders for each device
_DEVICE_DEFAULT_HOSTNAME: dict[DeviceType, str] = {
    DeviceType.BACTOBOX: "bbYYWWXXX",
    DeviceType.ZEUS: "zsYYWWXXX",
}


class DeviceDescription(FrozenModel):
    """Identifies a specific device by its type and link to the host."""

    # Kind/class of the device
    device_type: DeviceType
    # Version of the device
    device_version: constr(regex=r"[0-9][A-Za-z0-9-_.]+")
    # Connection to the device by which we can, e.g., turn it on and send data.
    link: DeviceLink
    # Metadata such as the device condition, firmware version, etc.
    metadata: DeviceMetadata = DeviceMetadata()
    # Hardware identifications
    hw_ids: Optional[HardwareIdentificationGroup] = Field(
        default=None, description="We add this in 11/2023 as a request from production"
    )

    @root_validator
    def _check_pcb_item_number(  # pylint: disable=no-self-argument
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        hw_ids: HardwareIdentificationGroup = values.get("hw_ids")
        if hw_ids is None:
            return values
        device_type = values.get("device_type")
        assert hw_ids.pcb_item_number in _DEVICE_PCB_ITEM_NUMBER[device_type], (
            f"{DeviceType.BACTOBOX} PCB identification number must "
            f"start with {_DEVICE_PCB_ITEM_NUMBER[device_type]}"
        )
        return values

    @classmethod
    def from_raw_args(
        cls,
        *,
        device_type: DeviceType,
        device_version: str,
        pcb_identification_number: Optional[str] = None,
        tty: Optional[Path] = None,
        jtag_usb_serial: Optional[str] = None,
        jtag_usb_hub_location: Optional[str] = None,
        jtag_usb_hub_port: Optional[str] = None,
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
        if pcb_identification_number is None:
            hw_ids = None
        else:
            hw_ids = HardwareIdentificationGroup(
                pcb_identification_number=pcb_identification_number
            )
        hostname = _DEVICE_DEFAULT_HOSTNAME[device_type]
        communication = DeviceCommunication(
            hostname=hostname,
            tty=tty,
            jtag_usb_serial=jtag_usb_serial,
            jtag_usb_hub_location=jtag_usb_hub_location,
            jtag_usb_hub_port=jtag_usb_hub_port,
        )
        link = DeviceLink(control=control, communication=communication)
        return cls(
            device_type=device_type,
            device_version=device_version,
            hw_ids=hw_ids,
            link=link,
        )
