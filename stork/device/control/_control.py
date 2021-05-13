from pydantic import BaseModel

from .boot_mode import BootModeControl, GpioBootModeControl
from .power import PowerControl, RelayPowerControl


class DeviceControl(BaseModel):
    """The host's hardware controls of a device."""

    power: PowerControl = RelayPowerControl(1)
    boot_mode: BootModeControl = GpioBootModeControl(15)

    class Config:  # pylint: disable=too-few-public-methods
        allow_mutation = False
