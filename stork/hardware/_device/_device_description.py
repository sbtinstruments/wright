from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ...util import get_first_tty, get_local_ip
from .._boot_mode import BootModeControl
from .._hardware import Hardware
from .._power import PowerControl


class DeviceDescription(BaseModel):
    """Description of a device and how it is connected."""

    hardware: Hardware
    power_control: PowerControl  # Use a frozen descriptor instead
    boot_mode_control: BootModeControl  # Use a frozen descriptor instead
    tty: Path = Field(default_factory=get_first_tty)
    tftp_host: str = Field(default_factory=get_local_ip)
    tftp_port: int = 6969

    class Config:  # pylint: disable=too-few-public-methods
        allow_mutation = False
