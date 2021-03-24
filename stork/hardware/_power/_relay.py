from __future__ import annotations
from ...relay_lib_seeed import relay_get_port_status, relay_off, relay_on
from ._power import PowerControl


class RelayPowerControl(PowerControl):
    def __init__(self, power_relay_num: int) -> None:
        self._relay_num = power_relay_num

    @property
    def on(self) -> bool:
        return relay_get_port_status(self._relay_num)

    @on.setter
    def on(self, value: bool) -> None:
        if value:
            relay_on(self._relay_num)
        else:
            relay_off(self._relay_num)

    def copy(self) -> RelayPowerControl:
        return RelayPowerControl(self._relay_num)