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
        super().__init__(device, tg, prompt, force_prompt_timeout=30)

    async def reset_data(self) -> None:
        """Remove all data on this device."""
        self.logger.info("Format data partition of MMC memory")
        # The umount command will fail if the data partition is invalid
        # or non-existing. Therefore, we skip the error code check.
        await self.cmd("umount /media/data", check_error_code=False)
        await self.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")

    async def _do_pre_prompt(self) -> None:
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

    async def _on_enter_post_prompt(self) -> None:
        self.logger.info('Kill any "sleep"-delayed startup scripts')
        # We stop all the services that may be using the /media/data path.
        # Kill any delayed scripts first.
        await self.cmd("kill `ps | awk '/[s]leep/ {print $1}'`")
        self.logger.info("Stop all processes that may use the data partition")
        await self.cmd("/etc/init.d/Amonit stop")
        await self.cmd("/etc/init.d/Adash stop")
        await self.cmd("/etc/init.d/Acellmate stop")
        await self.cmd("/etc/init.d/Abaxter stop")
        await self.cmd("/etc/init.d/Amester stop")
        await self.cmd("/etc/init.d/Amaskin stop")
        await self.cmd("/etc/init.d/S01rsyslogd stop")
        await self.cmd("/etc/init.d/S70swupdate stop")
        # We use an 'awk'-based kill command to make sure that even
        # launching processes are killed as well.
        await self.cmd("kill `ps | awk '/[t]elegraf/ {print $1}'`")
        await self.cmd("kill `ps | awk '/[i]nfluxd/ {print $1}'`")
