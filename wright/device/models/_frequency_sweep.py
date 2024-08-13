from __future__ import annotations

from typing import Any, Literal

from pydantic import model_validator

from ...model import FrozenModel


class FrequencySweep(FrozenModel):
    version: Literal["1.0.0"] = "1.0.0"
    frequencies: tuple[float, ...]
    site0: tuple[float, ...]
    site1: tuple[float, ...]

    @property
    def sites(self) -> tuple[tuple[float, ...], ...]:
        yield self.site0
        yield self.site1

    @model_validator(mode="after")
    def _dimensions_match(self) -> FrequencySweep:
        dimensions = (self.frequencies, self.site0, self.site1)
        lengths = iter(len(dimension) for dimension in dimensions)
        try:
            first_length = next(lengths)
        except StopIteration:
            return self
        if not all(length == first_length for length in lengths):
            raise ValueError("Frequencies and site values must have the same length")
        return self

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
