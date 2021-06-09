from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import anyio
from anyio.abc import TaskGroup

from ._base import _ConsoleBase
from ._uboot import Uboot

if TYPE_CHECKING:
    from .._green_mango import GreenMango


class Linux(_ConsoleBase):
    """The default linux distribution on the device."""

    def __init__(self, device: "GreenMango", tg: TaskGroup) -> None:
        communication = device.link.communication
        prompt = f"\r\n\x1b[1;34mroot@{communication.hostname}\x1b[m$ "
        super().__init__(
            device, tg, prompt, force_prompt_timeout=90, enter_force_prompt_delay=50
        )

    async def reset_data(self) -> None:
        """Remove all data on this device."""
        await self.stop_services_that_use_data_partition()
        await self.format_data_partition()

    async def stop_services_that_use_data_partition(self) -> None:
        """Stop all services that may use the data partition."""
        self.logger.info("Stop all services that may use the data partition")
        await self.cmd("/etc/init.d/S99monit stop")
        await self.cmd("/etc/init.d/S97dash stop")
        await self.cmd("/etc/init.d/S96staten stop")
        await self.cmd("/etc/init.d/S95mester stop")
        await self.cmd("/etc/init.d/S94baxter stop")
        await self.cmd("/etc/init.d/S93maskin stop")
        await self.cmd("/etc/init.d/S92cellmate stop")
        await self.cmd("/etc/init.d/S91frog stop")
        await self.cmd("/etc/init.d/S82telegraf stop")
        await self.cmd("/etc/init.d/S81influxdb stop")
        await self.cmd("/etc/init.d/S70swupdate stop")
        await self.cmd("/etc/init.d/S01rsyslogd stop")

    async def format_data_partition(self) -> None:
        """Format the data partition.

        This deletes all data.
        """
        self.logger.info("Format data partition of MMC memory")
        # The umount command will fail if the data partition is invalid
        # or non-existing. Therefore, we skip the error code check.
        await self.cmd("umount /media/data", check_error_code=False)
        await self.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")

    async def _on_enter_pre_prompt(self) -> None:
        await self._dev.hard_restart()
        # Wait a moment before we spam the serial line in search of the prompt.
        # Otherwise, we enter U-boot instead.
        await anyio.sleep(3)


class QuietLinux(Linux):
    """Linux with a quiet kernel log level."""

    async def _on_enter_pre_prompt(self) -> None:
        # Enter U-boot first so that we can set some boot flags for Linux to make
        # it quiet.
        async with Uboot.enter_context(self._dev) as uboot:
            await uboot.boot_to_quiet_linux()
