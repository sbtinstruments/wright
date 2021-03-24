from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...util import get_local_ip, get_first_tty
from .._boot_mode import BootModeControl
from .._hardware import Hardware
from .._power import PowerControl
from ._validation import raise_if_bad_hostname


@dataclass(frozen=True)
class BoardDefinition:
    hardware: Hardware
    power_control: PowerControl  # Use a frozen descriptor instead
    boot_mode_control: BootModeControl  # Use a frozen descriptor instead
    hostname: str
    tty: Path
    tftp_host: str
    tftp_port: int

    def __post_init__(self) -> None:
        raise_if_bad_hostname(self.hostname, self.hardware)

    @classmethod
    def with_defaults(
        cls,
        *,
        hardware: Hardware,
        power_control: PowerControl,
        boot_mode_control: BootModeControl,
        hostname: str,
        tty: Optional[Path] = None,
        tftp_host: Optional[str] = None,
        tftp_port: Optional[int] = None,
    ) -> BoardDefinition:

        if tty is None:
            tty = get_first_tty()
        if tftp_host is None:
            tftp_host = get_local_ip()
        if tftp_port is None:
            tftp_port = 6969

        return cls(
            hardware,
            power_control,
            boot_mode_control,
            hostname,
            tty,
            tftp_host,
            tftp_port,
        )
