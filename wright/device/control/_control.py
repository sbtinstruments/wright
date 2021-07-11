from ...model import FrozenModel
from .boot_mode import BootModeControl, GpioBootModeControl
from .power import PowerControl, RelayPowerControl


class DeviceControl(FrozenModel):
    """The host's hardware controls of a device."""

    power: PowerControl = RelayPowerControl(1)
    boot_mode: BootModeControl = GpioBootModeControl(15)
