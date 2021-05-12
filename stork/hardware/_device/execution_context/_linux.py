from __future__ import annotations

from typing import TYPE_CHECKING

from anyio.abc import TaskGroup

from ._base import _ConsoleBase
from ._uboot import Uboot

if TYPE_CHECKING:
    from .._green_mango import GreenMango


class Linux(_ConsoleBase):
    """The default linux distribution on the device."""

    def __init__(self, device: "GreenMango", tg: TaskGroup) -> None:
        prompt = f"\r\n\x1b[1;34mroot@{device.hostname}\x1b[m$ "
        super().__init__(device, tg, prompt)

    async def reset_data(self) -> None:
        """Remove all data on this device."""
        self.logger.info("Format data partition of MMC memory")
        # The umount command will fail if the data partition is invalid
        # or non-existing. Therefore, we skip the error code check.
        await self.cmd("umount /media/data", check_error_code=False)
        await self.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")


class QuietLinux(Linux):
    """Linux with a quiet kernel log level."""

    async def __aenter__(self) -> QuietLinux:
        # Enter U-boot first so that we can set some boot flags
        # for Linux to make it quiet.
        uboot = await self._dev.enter_context(Uboot)
        await uboot.boot_to_quiet_linux()
        # Enter the Linux console
        await super().__aenter__()
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
        return self
