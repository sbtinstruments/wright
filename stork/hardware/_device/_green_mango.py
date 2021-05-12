from __future__ import annotations

from contextlib import AsyncExitStack
from logging import Logger, getLogger
from types import TracebackType
from typing import Optional, Type

import anyio
from anyio.abc import TaskGroup
from anyio.lowlevel import checkpoint

from ._device_description import DeviceDescription
from ._execution_context_manager import ExecutionContextManager
from ._validation import raise_if_bad_hostname

_LOGGER = getLogger(__name__)


class GreenMango:
    """Device based on the SBT-developed Green Mango platform."""

    def __init__(
        self,
        tg: TaskGroup,
        hostname: str,
        desc: DeviceDescription,
        *,
        logger: Optional[Logger] = None,
    ) -> None:
        raise_if_bad_hostname(hostname, desc.hardware)
        # Public
        self.hostname: str = hostname
        self.desc = desc
        self.logger = logger if logger is not None else _LOGGER
        # Private
        self._stack: Optional[AsyncExitStack] = None
        self._power_control = desc.power_control
        self._boot_mode_control = desc.boot_mode_control
        self._execution_context_manager = ExecutionContextManager(
            self, tg, logger=self.logger
        )
        # Expose some specific methods
        self.scoped_boot_mode = self._boot_mode_control.scoped
        self.enter_context = self._execution_context_manager.enter_context

    async def hard_restart(self) -> None:
        """Restart this device via a power cycle."""
        self.logger.info("Restart device")
        await self.hard_power_off()
        self._power_on()

    async def hard_power_off(self) -> None:
        """Turn device off via a hard power cut."""
        # Early out if the power is already off
        if not self._power_control.get_state():
            self.logger.debug("Skipped hard power off (power was already off)")
            await checkpoint()
            return
        # Close the execution context (if any)
        await self._execution_context_manager.aclose()
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

    async def __aenter__(self) -> GreenMango:
        async with AsyncExitStack() as stack:
            stack.enter_context(self._power_control)
            stack.enter_context(self._boot_mode_control)
            await stack.enter_async_context(self._execution_context_manager)
            # Make sure that we power off on exit
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
