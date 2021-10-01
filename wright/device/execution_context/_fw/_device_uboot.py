from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from anyio.abc import TaskGroup

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

    def __init__(
        self,
        device: "Device",
        tg: TaskGroup,
        prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # Default arguments
        if prompt is None:
            # E.g. "bactobox>" or "zeus>" with some whitespace chars
            prompt = f"\r\n{type(device).__name__.lower()}> "
        super().__init__(device, tg, prompt, **kwargs)
        self._mmc = Mmc()

    @property
    def mmc(self) -> Mmc:
        """Return MMC partition overview for this device."""
        return self._mmc

    @deteriorate(DeviceCondition.USED)
    async def partition_mmc(self) -> None:
        """Partition the device's MMC memory."""
        self.logger.info("Partition MMC memory")
        await self.cmd(
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
