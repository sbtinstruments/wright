from __future__ import annotations

from dataclasses import dataclass

from ...relay_lib_seeed import relay_get_port_status, relay_off, relay_on
from ._abc import AbstractBootModeControl
from ._boot_mode import BootMode


@dataclass(frozen=True)
class RelayBootModeControl(AbstractBootModeControl):
    """Relay-based boot mode control."""

    relay_id: int
    default_mode: BootMode = BootMode.QSPI

    def get_mode(self) -> BootMode:
        """Return the current boot mode."""
        if relay_get_port_status(self.relay_id):
            return BootMode.JTAG
        return BootMode.QSPI

    def set_mode(self, value: BootMode) -> None:
        """Set the boot mode."""
        if value is BootMode.JTAG:
            relay_on(self.relay_id)
        elif value is BootMode.QSPI:
            relay_off(self.relay_id)
        else:
            raise ValueError("Could not set boot mode")
