from pathlib import Path

import matplotlib.pyplot as plt

from ...device.models import SignalIntegrityTest

# TODO: visualizing is not terminated
class ElecRefPlot:
    def __init__(self, si_test: SignalIntegrityTest):
        self._frequency_sweep = si_test.source_data

        fig, axs = plt.subplots(1, 2, sharey=True, figsize=(12, 6))
        fig.suptitle("Electronics reference (v3)")
        self._fig = fig

        for ax in axs:
            ax.grid(visible=True, alpha=0.3)
            ax.set_xscale("log")
            ax.set_xlabel("Frequency [MHz]")
            ax.set_ylabel("Amplitude [dB]")

        axs[0].set_title("Site 0")
        axs[1].set_title("Site 1")

        self.axs = axs
        self.up_th = [si_test.limits.max_gain] * 2
        self.low_th = [si_test.limits.min_gain] * 2
        self.min_bw = [si_test.limits.min_bandwidth * 1e-6] * 2
        self.features = si_test.features
        # Selecting low frequency threshold range
        self.frequencies_mhz = [
            self._frequency_sweep.frequencies[0] * 1e-6,
            self._frequency_sweep.frequencies[0] * 2e-6,
        ]

        self._plot()

    def _plot(self) -> None:
        self.plot_results()
        self.plot_reference()
        self.legend()

    def plot_results(self):
        kwargs_datapoints = {
            "color": "k",
            "marker": "x",
            "zorder": 100000,
        }
        frequencies_mhz = [f * 1e-6 for f in self._frequency_sweep.frequencies]
        for n, (site, feature) in enumerate(
            zip(self._frequency_sweep.sites, self.features.sites)
        ):
            self.axs[n].plot(frequencies_mhz, site, label="Device results")
            self.axs[n].scatter(
                feature.gain.frequency * 1e-6,
                feature.gain.amplitude,
                label="Gain",
                **kwargs_datapoints,
            )
            try:
                self.axs[n].scatter(
                    feature.bandwidth.frequency * 1e-6,
                    feature.bandwidth.amplitude,
                    label="Bandwidth",
                    **kwargs_datapoints,
                )
            except AttributeError:
                pass

    def plot_reference(self):
        for ax in self.axs:
            ax.plot(self.frequencies_mhz, self.low_th, "g", alpha=0.2)
            ax.plot(self.frequencies_mhz, self.up_th, "g", alpha=0.2)

            ax.fill_between(
                self.frequencies_mhz,
                self.low_th,
                self.up_th,
                color="green",
                alpha=0.1,
                label="Accept region",
            )

            ax.set_xlim([0.1, 25])

            # Emphasize minimum bandwidth
            ylims = ax.get_ylim()
            ax.plot(self.min_bw, ylims, "k--", alpha=0.3, label="Minimun BW")
            ax.set_ylim(ylims)

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
