from __future__ import annotations

from contextlib import AsyncExitStack
from logging import Logger, getLogger
from types import TracebackType
from typing import ContextManager, Optional, Type

import anyio
from anyio.lowlevel import checkpoint

from .._device import Device
from .._device_link import DeviceLink
from .._device_metadata import DeviceMetadata
from .._device_registry import add_device
from .._device_type import DeviceType
from ..control.boot_mode import BootMode

_LOGGER = getLogger(__name__)


class GreenMango(Device):
    """Device based on the SBT-developed Green Mango platform."""

    def __init__(
        self,
        version: str,
        link: DeviceLink,
        metadata: Optional[DeviceMetadata] = None,
        *,
        logger: Optional[Logger] = None,
    ) -> None:
        super().__init__(version, link, metadata, logger=logger)
        self._stack: Optional[AsyncExitStack] = None
        self._power_control = link.control.power
        self._boot_mode_control = link.control.boot_mode

    async def hard_power_off(self) -> None:
        """Turn device off via a hard power cut."""
        await super().hard_power_off()
        # Early out if the power is already off
        if not self._power_control.get_state():
            self.logger.debug("Skipped hard power off (power was already off)")
            await checkpoint()
            return
        # Turn the power off
        self.logger.info("Hard power off")
        self._power_control.set_state(False)
        # Wait a bit for the system to loose power. E.g., it may
        # take some time for the capacitors to fully drain.
        await anyio.sleep(0.1)

    def _power_on(self) -> None:
        """Turn device on."""
        self.logger.info("Power on")
        self._power_control.set_state(True)

    def scoped_boot_mode(self, value: BootMode) -> ContextManager[None]:
        """Switch to the given boot mode while in the context manager."""
        return self._boot_mode_control.scoped(value)

    async def __aenter__(self) -> GreenMango:
        async with AsyncExitStack() as stack:
            stack.enter_context(self._power_control)
            stack.enter_context(self._boot_mode_control)
            # Make sure that we power off on exit
            # TODO: Move to `Device`
            stack.push_async_callback(self.hard_power_off)
            # Transfer ownership to this instance
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        assert self._stack is not None
        await self._stack.__aexit__(exc_type, exc_value, traceback)


class Zeus(GreenMango):
    """Zeus device (aka CytoQuant)."""


class BactoBox(GreenMango):
    """BactoBox device."""


add_device(DeviceType.ZEUS.value, Zeus)
add_device(DeviceType.BACTOBOX.value, BactoBox)
