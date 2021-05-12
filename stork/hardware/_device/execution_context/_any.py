from typing import Union

from ._linux import Linux, QuietLinux
from ._stork_uboot import StorkUboot
from ._uboot import Uboot

Any = Union[Uboot, StorkUboot, Linux, QuietLinux]
