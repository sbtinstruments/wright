from typing import Union

from ._external_uboot import ExternalUboot
from ._linux import Linux, QuietLinux
from ._uboot import Uboot

Any = Union[Uboot, ExternalUboot, Linux, QuietLinux]
