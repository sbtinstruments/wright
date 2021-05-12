from typing import Union
from ._relay import RelayBootModeControl
from ._gpio import GpioBootModeControl

BootModeControl = Union[RelayBootModeControl, GpioBootModeControl]
