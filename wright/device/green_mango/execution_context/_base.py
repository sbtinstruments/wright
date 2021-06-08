from __future__ import annotations

import warnings
from contextlib import AsyncExitStack, asynccontextmanager
from logging import Logger
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    AsyncIterator,
    Optional,
    Type,
)

import anyio
from anyio.abc import TaskGroup

from ....console import Console

if TYPE_CHECKING:
    from .._green_mango import GreenMango


class _Base(AsyncContextManager["_Base"]):
    def __init__(self, device: "GreenMango", tg: TaskGroup) -> None:
        self._dev = device
        self._tg = tg
        self._logger = self._dev.logger
        self._entered = False
        self._exited = False

    @property
    def logger(self) -> Logger:
        return self._logger

    @classmethod
    @asynccontextmanager
    async def enter_context(
        cls, device: "GreenMango", *args: Any, **kwargs: Any
    ) -> AsyncIterator[_Base]:
        """Return a context manager that enters this execution context on the device.

        This is a convenience method that creates a `TaskGroup` internally. If you
        already have a `TaskGroup`, just call the constructor directly.
        """
        async with anyio.create_task_group() as tg:
            async with cls(device, tg, *args, **kwargs) as context:
                yield context
            tg.cancel_scope.cancel()

    @classmethod
    async def enter_and_return(
        cls, device: "GreenMango", *args: Any, **kwargs: Any
    ) -> None:
        """Enter this execution context and then return immediately.

        Useful if you want to prime a device. That is, if you want to boot
        a device into a given execution context (e.g., Linux) but not do
        any actual work before later.
        """
        # Early out if we are already in a context of the given type.
        if cls.is_entered(device):
            return
        # Enter the context and do nothing.
        async with cls.enter_context(device, *args, **kwargs):
            pass

    @classmethod
    def is_entered(cls, device: "GreenMango") -> bool:
        """Is the given device currently in an execution context of this type."""
        return device.context_type is cls

    def _raise_if_not_entered(self) -> None:
        if not self._entered:
            raise RuntimeError("You must enter the execution environment first.")

    def _raise_if_exited(self) -> None:
        if self._exited:
            raise RuntimeError("You exited this context and can't use it anymore.")

    def _skip_enter_steps(self) -> bool:
        # Skip the usual enter steps (boot sequence) if the device is already
        # in an execution context of our type. This can save us from, e.g., the
        # lengthy Linux boot sequence.
        return type(self).is_entered(self._dev)

    async def __aenter__(self) -> _Base:
        self._dev.context_type = type(self)
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._exited = True
        # Invalidate context if we exit with an error
        if exc_type is not None:
            self._dev.context_type = None

    def __del__(self) -> None:
        if self._entered and not self._exited:
            message = f"Forgot to exit execution context: {self}"
            warnings.warn(message, category=ResourceWarning)


class _ConsoleBase(_Base):
    def __init__(
        self,
        device: "GreenMango",
        tg: TaskGroup,
        prompt: str,
        *,
        force_prompt_timeout: Optional[int] = None,
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
        self._stack: Optional[AsyncExitStack] = None

    async def cmd(self, *args: Any, **kwargs: Any) -> Any:
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
        self._dev.context_type = None

    async def _on_enter_pre_prompt(self) -> None:
        pass

    async def _on_enter_post_prompt(self) -> None:
        pass

    async def _force_prompt(self) -> None:
        with anyio.fail_after(self._force_prompt_timeout):
            await self._console.force_prompt()

    async def __aenter__(self) -> _ConsoleBase:
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
            await self._force_prompt()
            # Mark as "entered" already, so that the post prompt step can
            # issue commands.
            await super().__aenter__()
            # Post prompt
            if not skip_enter_steps:
                await self._on_enter_post_prompt()
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
        try:
            await self._stack.__aexit__(exc_type, exc_value, traceback)
        finally:
            await super().__aexit__(exc_type, exc_value, traceback)
