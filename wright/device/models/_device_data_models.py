from __future__ import annotations

from enum import Enum, unique
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Literal, Optional

from pydantic import Extra, root_validator, BaseModel

from ...device._device_type import DeviceType
from ...model import FrozenModel

# TODO: save it on external json file
THRESHOLDS = {
    DeviceType.BACTOBOX: {
        "min_gain": -45.8,
        "max_gain": -40.3,
        "min_bandwidth": 2.3e6,
    },
    DeviceType.ZEUS: {
        "min_gain": -46.2,
        "max_gain": -40.5,
        "min_bandwidth": 3.5e6,
    },
}


@dataclass(frozen=True)
class Thresholds:
    min_gain: float
    max_gain: float
    min_bandwidth: float


class FrequencySweep(FrozenModel):
    version: Literal["1.0.0"] = "1.0.0"
    frequencies: tuple[float, ...]
    site0: tuple[float, ...]
    site1: tuple[float, ...]

    @property
    def sites(self) -> tuple[tuple[float, ...], ...]:
        yield self.site0
        yield self.site1

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


class DataPoint(FrozenModel):
    frequency: float
    amplitude: float


class GainBandwidth(FrozenModel):
    gain: DataPoint
    bandwidth: Optional[DataPoint]

    def is_accepted(self, limits: Thresholds):
        if self.bandwidth is None:
            return False
        if (
            not limits.max_gain > self.gain.amplitude > limits.min_gain
            or self.bandwidth.frequency < limits.min_bandwidth
        ):
            return False
        return True

    @classmethod
    def from_amplitudes(cls, amplitudes, *, frequencies):
        gain = DataPoint(frequency=frequencies[0], amplitude=amplitudes[0])
        bandwidth = cls._extract_bandwidth_from_data(
            frequencies,
            amplitudes,
        )
        return cls(gain=gain, bandwidth=bandwidth)

    @staticmethod
    def _extract_bandwidth_from_data(
        frequencies: tuple[float, ...], amplitudes: tuple[float, ...]
    ) -> Optional[DataPoint]:
        value_3dB = amplitudes[0] - 3
        if min(amplitudes) > value_3dB:
            return None
        else:
            bw = next(
                DataPoint(frequency=f, amplitude=s)
                for f, s in zip(frequencies, amplitudes)
                if s <= value_3dB
            )
            return bw


class TestFeatures(FrozenModel):
    sites: tuple[GainBandwidth, ...]

    def is_accepted(self, limits: Thresholds):
        return all(site.is_accepted(limits) for site in self.sites)

    @classmethod
    def from_frequency_sweep(cls, source_data: FrequencySweep):
        frequencies = source_data.frequencies
        sites = [
            GainBandwidth.from_amplitudes(amplitudes, frequencies=frequencies)
            for amplitudes in source_data.sites
        ]
        return cls(sites=tuple(sites))


class SignalIntegrityTest(FrozenModel):
    source_data: FrequencySweep
    limits: Thresholds

    @cached_property
    def features(self) -> TestFeatures:
        return TestFeatures.from_frequency_sweep(self.source_data)

    @cached_property
    def is_accepted(self) -> bool:
        return self.features.is_accepted(self.limits)

    @classmethod
    def from_frequency_sweep(cls, source_data: FrequencySweep, *, device: DeviceType):
        # TODO: import it from external json file
        limits = Thresholds(**THRESHOLDS[device])
        return cls(source_data=source_data, limits=limits)

    class Config:
        # While we wait for: https://github.com/samuelcolvin/pydantic/pull/2625
        arbitrary_types_allowed = True
        keep_untouched = (cached_property,)


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
