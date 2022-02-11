from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import anyio

from ....command_line import SerialCommandLine
from ..._device_condition import DeviceCondition
from .._deteriorate import deteriorate
from .._enter_context import enter_context
from .._fw import DeviceUboot
from ._linux import Linux
from ._log_in import force_log_in_over_serial


class WrightLiveLinux(Linux):
    """Live, tiny, and high-level execution context.

    Live, in the sense that:
     1. Operating system (kernel and rootfs) lives in memory per default.
     2. Operating systme (kernel and rootfs) is from an external source and not
        from the device itself.

    Point (2) above is key. Basically, this means that this execution context doesn't
    depend on the device state. In other words, it's independent of the operating
    system (kernel and rootfs) installed on the device (if any).

    This is ideal if you, e.g., want to format a file system partition.
    """

    @deteriorate(DeviceCondition.AS_NEW)
    async def unbock_data_partition(self) -> None:
        """Stop all processes/mounts that may use the data partition."""
        self.logger.info("Stop all services that may use the data partition")
        await self.run("/etc/init.d/syslog stop")
        self.logger.info("Unmount overlayfs mounts that link to the data partition")
        # Sometimes, the data partition doesn't exist already or is corrupted.
        # In this case, the following `umount`s fail. Therefore, we ignore the
        # error code.
        await self.run("umount /var/lib", check_error_code=False)
        await self.run("umount /var/log", check_error_code=False)

    async def _boot(self) -> None:
        async with enter_context(DeviceUboot, self.device) as uboot:
            await uboot.boot_to_wright_live_linux()

    @asynccontextmanager
    async def _serial_cm(self) -> AsyncIterator[SerialCommandLine]:
        communication = self.device.link.communication
        # TODO: Remove the path (the "~" part) from the prompt.
        # This is a change to the wright image itself. Otherwise,
        # we fail to recognize the prompt if the user changes the
        # current working directory. For now, we simply don't change the
        # current working directory.
        prompt = f"root@{communication.hostname}:~# "
        async with self._create_serial(prompt) as serial:
            if not self._should_skip_boot():
                # Wait until the serial prompt is just about to appear.
                # We found the length of this sleep empirically.
                await anyio.sleep(15)
                # The authentication is at the default values
                with anyio.fail_after(15):
                    await force_log_in_over_serial(serial, username="root", password="")
            # Spam 'echo' commands until the serial prompt appears
            with anyio.fail_after(30):
                await serial.force_prompt()
            yield serial
