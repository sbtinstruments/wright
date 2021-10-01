from typing import Union

from ._fw import DeviceUboot, Uboot, WrightLiveUboot
from ._os import DeviceLinux, Linux, WrightLiveLinux

Any = Union[Uboot, DeviceUboot, WrightLiveUboot, Linux, WrightLiveLinux, DeviceLinux]
