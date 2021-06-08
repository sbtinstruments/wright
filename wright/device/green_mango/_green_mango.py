from __future__ import annotations

from contextlib import AsyncExitStack
from logging import Logger, getLogger
from types import TracebackType
from typing import Any, Optional, Type

import anyio
from anyio.lowlevel import checkpoint

from .._device import Device
from .._device_condition import DeviceCondition
from .._device_description import DeviceDescription, DeviceLink
from .._device_type import DeviceType
from ._green_mango import execution_context

_LOGGER = getLogger(__name__)


class GreenMango(Device):
    """Device based on the SBT-developed Green Mango platform."""

    def __init__(
        self,
        link: DeviceLink,
        condition: Optional[DeviceCondition] = None,
        *,
        logger: Optional[Logger] = None,
    ) -> None:
        # Defaults
        if condition is None:
            condition = DeviceCondition.UNKNOWN
        super().__init__(link, logger=logger)
        self._stack: Optional[AsyncExitStack] = None
        self._power_control = link.control.power
        self._boot_mode_control = link.control.boot_mode
        # It's not the responsibility of this class to keep track of the execution
        # context. It's up to the user to manage the current execution context.
        # We simply provde the `context` variable as a convenience to help the user
        # keep track.
        # This class does, however, set `context` to `None` on, e.g., power off.
        self.context_type: Optional[Type[execution_context.Any]] = None
        # Similarly, `condition` is the responsibility of the user.
        self.condition = condition
        # Expose some specific methods
        self.scoped_boot_mode = self._boot_mode_control.scoped

    async def hard_power_off(self) -> None:
        """Turn device off via a hard power cut."""
        # Early out if the power is already off
        if not self._power_control.get_state():
            self.logger.debug("Skipped hard power off (power was already off)")
            await checkpoint()
            return
        # Reset the execution context
        self.context_type = None
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

    @staticmethod
    def from_description(description: DeviceDescription, **kwargs: Any) -> GreenMango:
        """Return device instance based on the given description."""
        try:
            cls = _TYPE_TO_CLASS[description.device_type]
        except KeyError as exc:
            raise ValueError(
                "Can't create a Green Mango device from the " "given description"
            ) from exc
        return cls(description.link, description.condition, **kwargs)

    def description(self) -> DeviceDescription:
        """Return description based on this device's current state."""
        device_type = _CLASS_TO_TYPE[type(self)]
        return DeviceDescription(
            device_type=device_type, link=self._link, condition=self.condition
        )


class Zeus(GreenMango):
    """Zeus device (aka CytoQuant)."""


class BactoBox(GreenMango):
    """BactoBox device."""


_TYPE_TO_CLASS = {
    DeviceType.ZEUS: Zeus,
    DeviceType.BACTOBOX: BactoBox,
}

_CLASS_TO_TYPE = {
    Zeus: DeviceType.ZEUS,
    BactoBox: DeviceType.BACTOBOX,
}
