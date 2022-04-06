from __future__ import annotations

from enum import Enum, unique
from typing import Any, Literal

from pydantic import Extra, root_validator

from ...model import FrozenModel


class FrequencySweep(FrozenModel):
    version: Literal["1.0.0"] = "1.0.0"
    frequencies: tuple[float, ...]
    site0: tuple[float, ...]
    site1: tuple[float, ...]

    @root_validator
    def _dimensions_match(  # pylint: disable=no-self-argument
        cls, values: dict[str, Any]
    ) -> dict[str, Any]:
        dimension_names = ("frequencies", "site0", "site1")
        lengths = iter(len(v) for k, v in values.items() if k in dimension_names)
        try:
            first_length = next(lengths)
        except StopIteration:
            return values
        if not all(length == first_length for length in lengths):
            raise ValueError("Frequencies and site values must have the same length")
        return values

    @classmethod
    def from_elec_ref_data(cls, elec_ref_data: dict[str, Any]) -> FrequencySweep:
        try:
            version = elec_ref_data["version"]
        except KeyError as exc:
            raise ValueError("Could not read version field") from exc
        if version != "1.0.0":
            raise ValueError(
                f'We do not support electronics reference data version "{version}"'
            )
        try:
            checks = elec_ref_data["checks"]
        except KeyError as exc:
            raise ValueError('Missing "checks" field') from exc
        try:
            frequencies = tuple(e["freq"] for e in checks)
            site0 = tuple(e["site0"] for e in checks)
            site1 = tuple(e["site1"] for e in checks)
        except KeyError as exc:
            raise ValueError('Missing field in "checks" array') from exc
        return cls(frequencies=frequencies, site0=site0, site1=site1)


@unique
class BbpState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_done(self) -> bool:
        """Is the given state either completed, failed, or cancelled."""
        return self in (BbpState.COMPLETED, BbpState.FAILED, BbpState.CANCELLED)


class PartialBbpStatus(FrozenModel):
    state: BbpState

    class Config:
        extra = Extra.ignore  # This is a partial model


class Process(FrozenModel):
    """Process summary as given back by `psutil`."""

    name: str
    cmdline: tuple[str, ...]
