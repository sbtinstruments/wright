from pydantic import constr, validator

from ...model import FrozenModel


# TODO: Rename to singlar noun
class HardwareIdentificationGroup(FrozenModel):
    """List of hardware components identification numbers within a device"""

    pcb_identification_number: constr(regex=r"[0-9]{12}")

    @property
    def pcb_item_number(self) -> int:
        return int(self.pcb_identification_number[:5])

    @validator("pcb_identification_number")
    def _check_week(cls, value: str) -> str:  # pylint: disable=no-self-argument
        week = int(value[7:9])
        if week > 53:
            raise ValueError("The week number must be less than or equal to 53.")
        return value
