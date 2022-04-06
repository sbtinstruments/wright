from __future__ import annotations

from contextlib import asynccontextmanager
from types import TracebackType
from typing import AsyncContextManager, AsyncIterator, Mapping, Optional, Type

import anyio
from anyio.streams.memory import MemoryObjectSendStream

from ._status import Cancelled, Completed, Failed, Idle, Running, Status

StatusMap = Mapping[str, Status]  # Ideally, this is an immutable mapping

StatusStream = MemoryObjectSendStream[StatusMap]


class ProgressManager(AsyncContextManager["ProgressManager"]):
    """Convenience context manager for progress reports."""

    def __init__(
        self,
        status_map: StatusMap,
        *,
        status_stream: Optional[StatusStream] = None,
    ) -> None:
        self._initial_status_map = status_map
        self._status_map = self._initial_status_map
        self._status_stream = status_stream

    @asynccontextmanager
    async def step(self, name: str) -> AsyncIterator[None]:
        """Mark the nested code as a step with the given name.

        Automatically sends out `Running`, `Cancelled`, `Failed`, etc.
        status messages.
        """
        await self._run(name)
        try:
            yield
        except anyio.get_cancelled_exc_class():
            with anyio.CancelScope(shield=True):
                await self._cancel(name)
            raise
        except (Exception, anyio.ExceptionGroup):
            with anyio.CancelScope(shield=True):
                await self._fail(name)
            raise
        else:
            await self._complete(name)

    async def skip(self, name: str) -> None:
        """Skip the step with the given name."""
        status = self._status_map[name]
        if not isinstance(status, Idle):
            raise RuntimeError('Can only skip from the "Idle" status.')
        self._status_map = {**self._status_map, name: status.skip()}
        await self._send_status_update()

    async def _run(self, name: str) -> None:
        status = self._status_map[name]
        if not isinstance(status, (Idle, Completed, Cancelled, Failed)):
            raise RuntimeError(
                'Can only run from the "Idle", "Completed", '
                '"Cancelled", or "Failed" status.'
            )
        self._status_map = {**self._status_map, name: status.run()}
        await self._send_status_update()

    async def _cancel(self, name: str) -> None:
        status = self._status_map[name]
        if not isinstance(status, Running):
            raise RuntimeError('Can only cancel from the "Running" status.')
        self._status_map = {**self._status_map, name: status.cancel()}
        await self._send_status_update()

    async def _complete(self, name: str) -> None:
        status = self._status_map[name]
        if not isinstance(status, Running):
            raise RuntimeError('Can only complete from the "Running" status.')
        self._status_map = {**self._status_map, name: status.complete()}
        await self._send_status_update()

    async def _fail(self, name: str) -> None:
        status = self._status_map[name]
        if not isinstance(status, Running):
            raise RuntimeError('Can only fail from the "Running" status.')
        self._status_map = {**self._status_map, name: status.fail()}
        await self._send_status_update()

    async def _send_status_update(self) -> None:
        if self._status_stream is not None:
            await self._status_stream.send(self._status_map)

    async def __aenter__(self) -> ProgressManager:
        self._status_map = self._initial_status_map
        await self._send_status_update()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        pass
