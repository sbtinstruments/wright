from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Optional

import anyio
from anyio.abc import TaskGroup

from ....command_line import SerialCommandLine
from ..._device_condition import DeviceCondition
from .._deteriorate import deteriorate
from .._enter_context import enter_context
from .._fw import DeviceUboot
from ._linux import Linux

if TYPE_CHECKING:
    from ..._device import Device


class DeviceLinux(Linux):
    """The Linux distribution installed on the device.

    This depends on the state of device. That is, the operating system (kernel
    and rootfs) installed on the device. Use `WrightLiveLinux` if you want a
    stateless execution context.
    """

    def __init__(
        self, device: "Device", tg: TaskGroup, kernel_log_level: Optional[int] = None
    ) -> None:
        super().__init__(device, tg)
        # Kernel logging messes with the serial output. That is, sometimes the
        # kernel will spam the serial line with driver info messages. Said
        # messages interfere with how we parse the serial line.
        # Use `kernel_log_level=0` to avoid this.
        self._kernel_log_level = kernel_log_level

    @deteriorate(DeviceCondition.AS_NEW)
    async def unbock_data_partition(self) -> None:
        """Stop all processes/mounts that may use the data partition."""
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
        # HACK: crond doesn't use the data partition but it causes other issues
        # due to sudden time shifts. Therefore, we also stop crond.
        # Specifically, a time shift during `mkfs.ext4` causes `mkfs.ext4` to
        # not return.
        await self.cmd("/etc/init.d/S60crond stop")
        # We introduced nginx in SW 4.12.0. Therefore, it won't be there on older
        # systems. Hence the conditional command.
        await self.cmd("[ -f /etc/init.d/S50nginx ] && /etc/init.d/S50nginx stop")
        await self.cmd("/etc/init.d/S01rsyslogd stop")

    @deteriorate(DeviceCondition.AS_NEW)
    async def get_processes(self) -> dict[int, str]:
        """Return overview of the processes that run on the device."""
        encoded = await self.py(_PY_PRINT_PROCESSES)
        return encoded

    async def _boot(self) -> None:
        # We assume that the device uses U-boot and sbtOS. This way, we know how to
        # enter Linux.

        # Enter U-boot first so that we can interrupt the usual boot procedure.
        # Otherwise, U-boot power offs early with the message:
        #
        #  > PMIC woke due to "charging" event'
        #
        # on battery-powered devices like Zeus.
        #
        # We need to set the boot flags for Linux (e.g., "log level") from within
        # U-boot anyhow.
        async with enter_context(DeviceUboot, self._dev) as uboot:
            if self._kernel_log_level is not None:
                await uboot.set_boot_args(loglevel="0")
            await uboot.boot_to_device_os()

    @asynccontextmanager
    async def _serial_cm(self) -> AsyncIterator[SerialCommandLine]:
        communication = self.device.link.communication
        # We assume that the device uses sbtOS for now. This way, we know what
        # the prompt looks like.
        prompt = f"\r\n\x1b[1;34mroot@{communication.hostname}\x1b[m$ "
        async with self._create_serial(prompt) as serial:
            if not self._should_skip_boot():
                # Wait until the serial prompt is just about to appear.
                # We found the length of this sleep empirically.
                await anyio.sleep(50)
            # Spam 'echo' commands until the serial prompt appears
            with anyio.fail_after(90):
                await serial.force_prompt()
            yield serial


_PY_PRINT_PROCESSES = """
import psutil;
processes = {
    p.pid: p.as_dict(attrs=['name', 'cmdline'])
    for p in psutil.process_iter()
};
print(processes)
""".replace(
    "\n", ""
)
