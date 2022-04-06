from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ...device import DeviceType
from ...device.models import FrequencySweep


class ElecRefPlot:
    def __init__(self, frequency_sweep: FrequencySweep, device_type: DeviceType):
        self._frequency_sweep = frequency_sweep

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
        if device_type is DeviceType.ZEUS:
            file = np.load("/media/data/shipyard/ref_v3_zs.npz")
        elif device_type is DeviceType.BACTOBOX:
            file = np.load("/media/data/shipyard/ref_v3_bb.npz")
        else:
            raise RuntimeError("There is no reference file for this device type.")
        (freq, low_th, up_th) = file.values()
        self.freq = freq
        self.up_th = up_th
        self.low_th = low_th
        self._plot()

    def _plot(self) -> None:
        self.plot_reference()
        self.plot_results(
            self._frequency_sweep.frequencies,
            self._frequency_sweep.site0,
            self._frequency_sweep.site1,
        )
        self.legend()

    def plot_results(self, freqs, values_site0, values_site1):
        self.axs[0].plot(np.array(freqs) * 1e-6, values_site0, label="Device results")
        self.axs[1].plot(np.array(freqs) * 1e-6, values_site1, label="Device results")

    def plot_reference(self):
        for ax in self.axs:
            ax.plot(self.freq * 1e-6, self.low_th, "g", alpha=0.2)
            ax.plot(self.freq * 1e-6, self.up_th, "g", alpha=0.2)

            ax.fill_between(
                self.freq * 1e-6,
                self.low_th,
                self.up_th,
                color="green",
                alpha=0.1,
                label="Accept region",
            )

            ax.set_xlim([0.1, 25])

            # Emphasize two specific frequencies
            ylims = ax.get_ylim()
            ax.plot([1.9, 1.9], ylims, "k--", alpha=0.3, label="1.9 MHz")
            ax.plot([7, 7], ylims, "k:", alpha=0.3, label="7.0 MHz")
            # ax.set_ylim(ylims)

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
