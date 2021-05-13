from __future__ import annotations

import warnings
from contextlib import AsyncExitStack
from logging import Logger
from types import TracebackType
from typing import TYPE_CHECKING, Any, AsyncContextManager, Optional, Type

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

    def _raise_if_not_entered(self) -> None:
        if not self._entered:
            raise RuntimeError("You must enter the execution environment first.")

    def _raise_if_exited(self) -> None:
        if self._exited:
            raise RuntimeError("You exited this context and can't use it anymore.")

    async def __aenter__(self) -> _Base:
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._exited = True

    def __del__(self) -> None:
        if self._entered and not self._exited:
            message = f"Forgot to exit execution context: {self}"
            warnings.warn(message, category=ResourceWarning)


class _ConsoleBase(_Base):
    def __init__(self, device: "GreenMango", tg: TaskGroup, prompt: str) -> None:
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
        self._raise_if_not_entered()
        self._raise_if_exited()
        assert self._stack is not None
        await self._stack.aclose()

    async def __aenter__(self) -> _ConsoleBase:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(self._console)
            await self._console.force_prompt()
            # Transfer ownership to this instance
            self._stack = stack.pop_all()
        self._entered = True
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
            self._exited = True
