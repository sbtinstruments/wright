from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from anyio.abc import TaskGroup

from ..._device_condition import DeviceCondition
from .._deteriorate import deteriorate
from .._enter_context import enter_context
from .._fw import DeviceUboot
from ._linux import Linux

if TYPE_CHECKING:
    from ..._device import Device


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

    def __init__(
        self,
        device: "Device",
        tg: TaskGroup,
        prompt: Optional[str] = None,
        *,
        enter_force_prompt_delay: Optional[float] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # Default arguments
        if prompt is None:
            communication = device.link.communication
            # TODO: Remove the path (the "~" part) from the prompt.
            # This is a change to the wright image itself. Ohterwise,
            # we fail to recognize the prompt if the user changes the
            # current working directory. For now, we simply don't change the
            # current working directory.
            prompt = f"\r\nroot@{communication.hostname}:~# "
        if enter_force_prompt_delay is None:
            enter_force_prompt_delay = 15
        if username is None:
            username = "root"
        if password is None:
            password = ""
        super().__init__(
            device,
            tg,
            prompt,
            **kwargs,
            enter_force_prompt_delay=enter_force_prompt_delay,
            username=username,
            password=password,
        )

    @deteriorate(DeviceCondition.AS_NEW)
    async def unbock_data_partition(self) -> None:
        """Stop all processes/mounts that may use the data partition."""
        self.logger.info("Stop all services that may use the data partition")
        await self.cmd("/etc/init.d/syslog stop")
        self.logger.info("Unmount overlayfs mounts that link to the data partition")
        await self.cmd("umount /var/lib")
        await self.cmd("umount /var/log")

    async def _on_enter_pre_prompt(self) -> None:
        async with enter_context(DeviceUboot, self._dev) as uboot:
            await uboot.boot_to_wright_live_linux()
