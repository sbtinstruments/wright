from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field

from ...device.models import Branding
from ...device import DeviceDescription, DeviceType
from ...model import FrozenModel
from ._low_level_config import LowLevelConfig
from ._reset_params import ResetParams


class RunParameters(FrozenModel):
    device_type: DeviceType
    device_version: str
    swu_file: Path
    branding: Branding
    pcb_identification_number: Optional[str] = Field(
        default=None,
        description=(
            "We add the PCB identification"
            "number on 11/2023 as a request from production"
        ),
    )
    hostname: Optional[str] = Field(
        default=None,
        description=(
            "We no longer use it since 11/2023"
            "but we keep it to make it backwards compatible with the"
            "history screen"
        ),
    )

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
            pcb_identification_number=self.pcb_identification_number,
            tty=low_level_config.tty,
            jtag_usb_serial=low_level_config.jtag_usb_serial,
            jtag_usb_hub_location=low_level_config.jtag_usb_hub_location,
            jtag_usb_hub_port=low_level_config.jtag_usb_hub_port,
            power_relay=low_level_config.power_relay,
            boot_mode_gpio=low_level_config.boot_mode_gpio,
        )

    def with_next_pcb_id(self) -> RunParameters:
        """Return copy with `hostname` set as per current time and parameters."""
        # We just assume that the hostname has a valid device type abbreviation for now.
        item_number = self.pcb_identification_number[:5]  # E.g.: "bb" as in BactoBox
        year = self.pcb_identification_number[5:7]  # E.g.: "22" as in year 2022
        week = self.pcb_identification_number[7:9]  # E.g.: "47" as in week 47
        # TODO: Handle roll-over. That is, what happens after 999?
        id_ = int(self.pcb_identification_number[-3:]) + 1
        pcb_identification_number = f"{item_number}{year}{week}{id_:03}"
        return self.update(pcb_identification_number=pcb_identification_number)
