from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

import anyio
from anyio.abc import TaskGroup

from ....command_line import SerialCommandLine
from ..._device_condition import DeviceCondition
from .._deteriorate import deteriorate
from ._mmc import Mmc
from ._uboot import Uboot

if TYPE_CHECKING:
    from ..._device import Device


class DeviceUboot(Uboot):
    """The U-boot distribution installed on the device.

    This depends on the state of device. That is, the firmware (bootloader(s))
    installed on the device. Use `WrightLiveUboot` if you want a stateless
    execution context.
    """

    def __init__(self, device: "Device", tg: TaskGroup) -> None:
        super().__init__(device, tg)
        self._mmc = Mmc()

    @property
    def mmc(self) -> Mmc:
        """Return MMC partition overview for this device."""
        return self._mmc

    @deteriorate(DeviceCondition.USED)
    async def partition_mmc(self) -> None:
        """Partition the device's MMC memory."""
        self.logger.info("Partition MMC memory")
        await self.run(
            'gpt write mmc 0 "'
            "name=system0,size=150MiB;"
            "name=system1,size=150MiB;"
            "name=config,size=100MiB;"
            'name=data,size=0"'
        )
        # U-boot won't recognize the new partitioning right away.
        # No combination of `mmc dev 0`, `mmc rescan`, etc. will do.
        # We need to restart the entire device. Therefore, we close
        # this context.
        await self.aclose()

    async def _boot(self) -> None:
        await self.device.hard_restart()

    @asynccontextmanager
    async def _serial_cm(self) -> AsyncIterator[SerialCommandLine]:
        # E.g. "bactobox>" or "zeus>" with some whitespace chars
        prompt = f"{type(self.device).__name__.lower()}> "
        async with self._create_serial(prompt) as serial:
            # Spam 'echo' commands until the serial prompt appears
            with anyio.fail_after(5):
                await serial.force_prompt()
            yield serial
