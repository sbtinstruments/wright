from __future__ import annotations

from datetime import datetime

from pydantic import FilePath

from ...config.branding import Branding
from ...device import DeviceDescription, DeviceType
from ...model import FrozenModel
from ._low_level_config import LowLevelConfig
from ._reset_params import ResetParams


class RunParameters(FrozenModel):
    device_type: DeviceType
    device_version: str
    hostname: str
    swu_file: FilePath
    branding: Branding

    @property
    def reset_params(self) -> ResetParams:
        return ResetParams(
            device_description=self.device_description,
            swu_file=self.swu_file,
            branding=self.branding,
        )

    @property
    def device_description(self) -> DeviceDescription:
        low_level_config = LowLevelConfig.try_from_config_file()
        return DeviceDescription.from_raw_args(
            device_type=self.device_type,
            device_version=self.device_version,
            hostname=self.hostname,
            tty=low_level_config.tty,
            jtag_usb_serial=low_level_config.jtag_usb_serial,
            power_relay=low_level_config.power_relay,
            boot_mode_gpio=low_level_config.boot_mode_gpio,
        )

    def with_next_hostname(self) -> RunParameters:
        """Return copy with `hostname` set as per current time and parameters."""
        # We just assume that the hostname has a valid device type abbreviation for now.
        device_abbr = self.hostname[:2]  # E.g.: "bb" as in BactoBox
        now = datetime.now()
        # Use the ISO version to ensure standardized fields. E.g., week numbers.
        now_iso = now.isocalendar()
        year = str(now_iso[0])[2:]  # E.g.: "21" as in 2021
        week = now_iso[1]  # E.g.: `42`
        # TODO: Handle roll-over. That is, what happens after 999?
        id_ = int(self.hostname[-3:]) + 1
        hostname = f"{device_abbr}{year}{week:02}{id_:03}"
        return self.update(hostname=hostname)
