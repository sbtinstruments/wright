from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import markers

from ..device.models import ElecRef


_GAIN_COLOR = "teal"
_BANDWIDTH_COLOR = "purple"


class ElecRefPlot:
    def __init__(self, elec_ref: ElecRef):
        self._frequency_sweep = elec_ref.source_data

        fig, axs = plt.subplots(1, 2, sharey=True, figsize=(12, 6))
        fig.suptitle("Electronics reference")
        self._fig = fig

        for ax in axs:
            ax.grid(visible=True, alpha=0.3)
            ax.set_xscale("log")
            ax.set_xlabel("Frequency [MHz]")
            ax.set_ylabel("Amplitude [dB]")

        axs[0].set_title("Site 0")
        axs[1].set_title("Site 1")

        self.axs = axs
        rule_set = elec_ref.rule_set
        self.up_th = rule_set.max_gain
        self.low_th = rule_set.min_gain
        self.min_bw = rule_set.min_bandwidth * 1e-6
        self.features = elec_ref.features
        # Selecting low frequency threshold range
        self.frequencies_mhz = [
            self._frequency_sweep.frequencies[0] * 1e-6,
            self._frequency_sweep.frequencies[0] * 2e-6,
        ]

        self._plot()

    def _plot(self) -> None:
        self.plot_sweep()
        self.plot_rule_sets()
        self.plot_features()
        self.legend()

    def plot_features(self):
        marker_size = 400
        for n, feature in enumerate(self.features.sites):
            # Gain
            self.axs[n].scatter(
                feature.gain.frequency * 1e-6,
                feature.gain.amplitude,
                s=marker_size,
                marker=markers.CARETRIGHT,
                color=_GAIN_COLOR,
                clip_on=False,
                zorder=5,
            )
            self.axs[n].plot(
                [
                    self.axs[n].get_xlim()[0],
                    self.axs[n].get_xlim()[1],
                ],
                [
                    feature.gain.amplitude,
                    feature.gain.amplitude,
                ],
                "--",
                alpha=0.5,
                color=_GAIN_COLOR,
                zorder=5,
                label="Gain",
            )

            # Bandwidth
            if feature.bandwidth is None:
                continue
            self.axs[n].scatter(
                feature.bandwidth.frequency * 1e-6,
                self.axs[n].get_ylim()[0],
                s=marker_size,
                marker=markers.CARETUP,
                color=_BANDWIDTH_COLOR,
                clip_on=False,
                zorder=5,
            )
            self.axs[n].plot(
                [
                    feature.bandwidth.frequency * 1e-6,
                    feature.bandwidth.frequency * 1e-6,
                ],
                [
                    self.axs[n].get_ylim()[0],
                    self.axs[n].get_ylim()[1],
                ],
                "--",
                alpha=0.5,
                color=_BANDWIDTH_COLOR,
                zorder=5,
                label="Bandwidth",
            )

    def plot_sweep(self) -> None:
        frequencies_mhz = [f * 1e-6 for f in self._frequency_sweep.frequencies]
        for n, sweep in enumerate(self._frequency_sweep.sites):
            self.axs[n].plot(frequencies_mhz, sweep, "k", label="Device results")

    def plot_rule_sets(self) -> None:
        xlim_min = 0.1
        xlim_max = 25
        for ax in self.axs:
            # Gain
            ax.set_xlim([xlim_min, xlim_max])
            ax.fill_between(
                [xlim_min, xlim_max],
                self.low_th,
                self.up_th,
                color=_GAIN_COLOR,
                alpha=0.1,
                label="Acceptable gain",
                clip_on=False,
            )

            # Bandwidth
            ylims = ax.get_ylim()
            ax.set_ylim(ylims)  # Fixate ylims
            ax.fill_between(
                [self.min_bw, xlim_max],
                ylims[0],
                ylims[1],
                color=_BANDWIDTH_COLOR,
                alpha=0.1,
                label="Acceptable bandwidth",
                clip_on=False,
            )

    def legend(self):
        for ax in self.axs:
            ax.legend()

    def save(
        self,
        file: Path,
    ) -> None:
        self._fig.savefig(str(file))

    def show(self):
        plt.show()
