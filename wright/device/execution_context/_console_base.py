from contextlib import AsyncExitStack
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar, cast

import anyio
from anyio.abc import TaskGroup

from ...console import Console
from ._base import Base

if TYPE_CHECKING:
    from .._device import Device

Derived = TypeVar("Derived", bound="Base")


class ConsoleBase(Base):
    """Execution context that sends commands over a serial console."""

    def __init__(
        self,
        device: "Device",
        tg: TaskGroup,
        prompt: str,
        *,
        force_prompt_timeout: Optional[int] = None,
        enter_force_prompt_delay: Optional[float] = None,
    ) -> None:
        super().__init__(device, tg)
        # Logger for the console
        if self._logger is None:
            console_logger = None
        else:
            console_logger = self._logger.getChild("console")
        # Console
        self._console = Console(
            self._tg,
            self._dev.link.communication.tty,
            prompt,
            logger=console_logger,
        )
        self._force_prompt_timeout = force_prompt_timeout
        if enter_force_prompt_delay is None:
            enter_force_prompt_delay = 0
        self._enter_force_prompt_delay = enter_force_prompt_delay
        self._stack: Optional[AsyncExitStack] = None

    async def cmd(self, *args: Any, **kwargs: Any) -> Optional[str]:
        """Send command through the console."""
        self._raise_if_not_entered()
        self._raise_if_exited()
        return await self._console.cmd(*args, **kwargs)

    async def soft_reset(self) -> None:
        """Send 'reset' command but do not wait for acknowledgement."""
        await self.cmd("reset", wait_for_prompt=False)

    async def aclose(self) -> None:
        """Close this context.

        Use this if you issued a command that invalidates the commend. E.g., if you
        boot into Linux from U-boot.
        """
        self._raise_if_not_entered()
        self._raise_if_exited()
        assert self._stack is not None
        await self._stack.aclose()
        self._dev.metadata = self._dev.metadata.update(execution_context=None)

    async def _on_enter_pre_prompt(self) -> None:
        pass

    async def _on_enter_post_prompt(self) -> None:
        pass

    async def _force_prompt(self) -> None:
        with anyio.fail_after(self._force_prompt_timeout):
            await self._console.force_prompt()

    async def __aenter__(self) -> Derived:
        skip_enter_steps = self._skip_enter_steps()
        # Log if we skip some steps
        if skip_enter_steps:
            self._logger.info(
                "Already in %s. We skip the usual boot sequence.",
                type(self).__name__,
            )
        # Pre prompt
        if not skip_enter_steps:
            await self._on_enter_pre_prompt()
        async with AsyncExitStack() as stack:
            # Prompt
            await stack.enter_async_context(self._console)
            if not skip_enter_steps:
                await anyio.sleep(self._enter_force_prompt_delay)
            await self._force_prompt()
            # Mark as "entered" already, so that the post prompt step can
            # issue commands.
            await super().__aenter__()
            # Post prompt
            if not skip_enter_steps:
                await self._on_enter_post_prompt()
            # Transfer ownership to this instance
            self._stack = stack.pop_all()
        return cast(Derived, self)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        assert self._stack is not None
        try:
            await self._stack.__aexit__(exc_type, exc_value, traceback)
        finally:
            await super().__aexit__(exc_type, exc_value, traceback)
