from __future__ import annotations

from typing import Literal, Optional

from ...device._device_type import DeviceType
from ...model import FrozenModel
from ._frequency_sweep import FrequencySweep


class ElecRuleSet(FrozenModel):
    version: Literal["1.0.0"] = "1.0.0"
    min_gain: float
    max_gain: float
    min_bandwidth: float


# TODO: Save in an external json file
ELEC_RULE_SETS = {
    DeviceType.BACTOBOX: ElecRuleSet(
        min_gain=-45.8,
        max_gain=-40.3,
        min_bandwidth=2.3e6,
    ),
    DeviceType.ZEUS: ElecRuleSet(
        min_gain=-46.2,
        max_gain=-40.5,
        min_bandwidth=3.5e6,
    ),
}

class DataPoint(FrozenModel):
    frequency: float
    amplitude: float


class GainBandwidth(FrozenModel):
    gain: DataPoint
    bandwidth: Optional[DataPoint]

    def is_accepted(self, rule_set: ElecRuleSet):
        if self.bandwidth is None:
            return False
        if (
            not rule_set.max_gain > self.gain.amplitude > rule_set.min_gain
            or self.bandwidth.frequency < rule_set.min_bandwidth
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
        return next(
            DataPoint(frequency=f, amplitude=s)
            for f, s in zip(frequencies, amplitudes)
            if s <= value_3dB
        )


class ElecFeatures(FrozenModel):
    """Features relevant for the signal integrity test."""
    sites: tuple[GainBandwidth, ...]

    def is_accepted(self, rule_set: ElecRuleSet):
        return all(site.is_accepted(rule_set) for site in self.sites)

    @classmethod
    def from_frequency_sweep(cls, source_data: FrequencySweep):
        frequencies = source_data.frequencies
        sites = tuple(
            GainBandwidth.from_amplitudes(amplitudes, frequencies=frequencies)
            for amplitudes in source_data.sites
        )
        return cls(sites=sites)
