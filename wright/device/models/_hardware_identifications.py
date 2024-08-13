from typing import Annotated

from pydantic import AfterValidator, Field

from ...model import FrozenModel


def _validate_week(value: str) -> str:
    week = int(value[7:9])
    if week > 53:
        raise ValueError("The week number must be less than or equal to 53.")
    return value


PcbIdNumber = Annotated[
    str, Field(pattern=r"[0-9]{12}"), AfterValidator(_validate_week)
]


class HardwareIdentificationGroup(FrozenModel):
    """List of hardware components identification numbers within a device"""

    pcb_identification_number: PcbIdNumber

    @property
    def pcb_item_number(self) -> int:
        return int(self.pcb_identification_number[:5])
