from __future__ import annotations

import asyncio
from asyncio.tasks import Task
from contextlib import suppress
from asyncio.subprocess import PIPE, Process, STDOUT
from types import TracebackType
from typing import Callable, IO, Optional, Type, Union

from asyncio.exceptions import CancelledError


class Subprocess:
    def __init__(
        self,
        program: str,
        *args: str,
        stdin: Union[int, IO, None] = None,
        raise_on_rc: Optional[bool] = None,
        terminate_on_exit: Optional[bool] = None,
        output_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._program = program
        self._args = args
        self._stdin = stdin
        if raise_on_rc is None:
            raise_on_rc = True
        self._raise_on_rc = raise_on_rc
        if terminate_on_exit is None:
            terminate_on_exit = False
        self._terminate_on_exit = terminate_on_exit
        self._output_cb: Optional[Callable[[str], None]] = output_cb
        self._process: Optional[Process] = None
        self._read_task: Optional[Task] = None

    @classmethod
    async def run(cls, *args, **kwargs) -> None:
        """Run a subprocess to completion."""
        async with cls(*args, **kwargs):
            pass

    async def _read(self) -> None:
        while True:
            stdout_line = await self._process.stdout.readline()
            if stdout_line == b"":
                break
            if self._output_cb is not None:
                self._output_cb(stdout_line.decode())

    async def _cancel_tasks(self) -> None:
        if self._read_task is not None:
            self._read_task.cancel()
            with suppress(CancelledError):
                await self._read_task

    async def _start(self) -> None:
        assert self._process is None
        self._process = await asyncio.create_subprocess_exec(
            self._program, *self._args, stdin=self._stdin, stdout=PIPE, stderr=STDOUT
        )
        assert self._read_task is None
        self._read_task = asyncio.create_task(self._read())

    def terminate(self) -> None:
        self._process.terminate()

    async def __aenter__(self) -> Subprocess:
        await self._start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        if self._terminate_on_exit:
            try:
                self.terminate()
            except ProcessLookupError:
                # Ignore if the process is already done
                pass
        rc = await self._process.wait()
        await self._cancel_tasks()
        if self._raise_on_rc and rc != 0:
            raise RuntimeError(f"Process returned non-zero code: {rc}")
