from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import anyio
from anyio.abc import TaskGroup

from ._console_base import ConsoleBase
from ._enter_context import enter_context
from ._uboot import Uboot

if TYPE_CHECKING:
    from .._device import Device


class Linux(ConsoleBase):
    """The default linux distribution on the device."""

    def __init__(self, device: "Device", tg: TaskGroup) -> None:
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

    async def get_date(self) -> datetime:
        """Return the device date."""
        date_str = await self.cmd("date +%s")
        assert date_str is not None
        return datetime.utcfromtimestamp(int(date_str))

    async def get_versions(self) -> dict[str, str]:
        """Return the versions of all installed firmware, software, etc."""
        raw_versions = await self.cmd("cat /etc/sw-versions")
        assert raw_versions is not None
        result: dict[str, str] = dict()
        lines = raw_versions.split("\n")
        for line in lines:  # Example `line`: "firmware 3.2.0"
            words = line.strip().split(" ")  # Example `words`: ["firmware", "3.2.0"]
            # Skip invalid lines
            if len(words) != 2:
                continue
            result[words[0]] = words[1]
        return result

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
        async with enter_context(Uboot, self._dev) as uboot:
            await uboot.boot_to_quiet_linux()
