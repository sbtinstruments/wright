from __future__ import annotations
from ._boot_mode import BootMode, BootModeControl

from ...relay_lib_seeed import relay_get_port_status, relay_off, relay_on


class RelayBootModeControl(BootModeControl):
    def __init__(self, relay_num: int) -> None:
        self._relay_num = relay_num

    @property
    def mode(self) -> BootMode:
        if relay_get_port_status(self._relay_num):
            return BootMode.JTAG
        else:
            return BootMode.QSPI

    @mode.setter
    def mode(self, value: BootMode) -> None:
        if value is BootMode.JTAG:
            relay_on(self._relay_num)
        elif value is BootMode.QSPI:
            relay_off(self._relay_num)
        else:
            raise ValueError("Could not set boot mode")

    def copy(self) -> RelayBootModeControl:
        return RelayBootModeControl(self._relay_num)
