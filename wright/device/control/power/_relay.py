from __future__ import annotations

from dataclasses import dataclass

from ....relay_lib_seeed import relay_get_port_status, relay_off, relay_on
from ._abc import AbstractPowerControl


@dataclass(frozen=True)
class RelayPowerControl(AbstractPowerControl):
    """Relay-based power control."""

    relay_id: int
    default_state: bool = False

    def get_state(self) -> bool:
        """Is the power on."""
        return relay_get_port_status(self.relay_id)

    def set_state(self, value: bool) -> None:
        """Turn the power on (True) or off (False)."""
        if value:
            relay_on(self.relay_id)
        else:
            relay_off(self.relay_id)
