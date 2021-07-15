from __future__ import annotations

import itertools
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from math import inf
from pathlib import Path
from types import TracebackType
from typing import Any, AsyncIterator, Optional, Type

import anyio
import serial
from anyio.abc import TaskGroup, TaskStatus
from anyio.lowlevel import checkpoint

from .util import DelimitedBuffer

_LOGGER = logging.getLogger(__name__)


class Console:
    """Serial console used to send commands to the device.

    Works both in U-boot and Linux.
    """

    def __init__(
        self,
        tg: TaskGroup,
        tty: Path,
        prompt: str,
        *,
        baud_rate: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ):
        # Argument defaults
        if baud_rate is None:
            baud_rate = 115200
        if logger is None:
            logger = _LOGGER
        # Note that we intentionally do not give the `port` argument to
        # `Serial.__init__`. This is because the constructor opens the port if given
        # and we want to defer that.
        self._serial = serial.Serial(baudrate=baud_rate)
        self._serial.port = str(tty)
        # Internals
        self._tg = tg
        self._cancel_scope = anyio.CancelScope()
        self._logger = logger
        self._prompt = prompt
        (
            self._responses_send,
            self._responses_receive,
        ) = anyio.create_memory_object_stream(
            inf, str
        )  # [1]
        # TODO: Submit a pull request to anyio that adds types to `anyio.Lock`.
        self._serial_lock = anyio.Lock()

    @classmethod
    @asynccontextmanager
    async def run_in_background(
        cls, *args: Any, **kwargs: Any
    ) -> AsyncIterator[Console]:
        """Create a console and run it in the background.

        This is a convenience method that creates a `TaskGroup` internally.
        """
        async with anyio.create_task_group() as tg:
            async with cls(tg, *args, **kwargs) as console:
                yield console

    async def force_prompt(self) -> None:
        """Force the prompt to appear.

        This is done by continuously spamming the console via the serial
        connection. During boot, any message will halt the boot sequence
        and show the prompt.

        We use this during boot to interrupt the boot process and enter,
        e.g., the U-boot console.
        """
        # Spam the serial line with simple "echo" commands.
        for i in itertools.count():  # Infinite range
            # Each command is unique (uses a different `i`) so that we
            # can distinguish them. Otherwise, the `cmd` call may mistake
            # a previous result as its own.
            try:
                # Use a small timeout so that we really do spam the
                # line and are able to interrupt a boot process.
                with anyio.fail_after(0.1):
                    resp = await self.cmd(f"echo {i}")
            except (RuntimeError, TimeoutError):
                # If the command fails we simply try again
                continue
            # If we get an invalid response, we try again.
            if resp != str(i):
                continue
            # If we got this far, we have successfully entered a command
            # and recieved the appropriate response. This means that we
            # are at the prompt.
            return

    async def wait_for_prompt(self) -> str:
        """Wait for the prompt to appear.

        Return the last response seen in the serial input. That is, the
        input since the last prompt occurred.
        """
        # Wait for a response. Whenever the prompt appears in the serial
        # input, we get a response.
        result = await self._responses_receive.receive()
        # Sometimes, there may be multiple responses. E.g., when we spam
        # the serial line in an attempt to interrupt a boot process.
        #
        # We overcome this situation by simply emptying the entire queue
        # and returning the last element. This discards all other elements
        # in the queue.
        while True:
            try:
                result = self._responses_receive.receive_nowait()
            except anyio.WouldBlock:
                break
        return result

    async def cmd(
        self, cmd: str, *, wait_for_prompt: bool = True, check_error_code: bool = True
    ) -> Optional[str]:
        """Send command."""
        resp = await self._cmd(cmd, wait_for_prompt=wait_for_prompt)
        # Early out
        if not wait_for_prompt or not check_error_code:
            return resp
        # Check error code
        error_code = await self._cmd("echo $?")
        assert error_code is not None
        if error_code.strip() != "0":
            raise RuntimeError(f"Command failed with error code {error_code}")
        return resp

    async def _cmd(self, cmd: str, *, wait_for_prompt: bool = True) -> Optional[str]:
        async with self._serial_lock:
            # Add line end so that the command is executed
            self._serial.write((cmd + "\n").encode())
        # Early out
        if not wait_for_prompt:
            return None
        resp = await self.wait_for_prompt()
        # raw = resp.encode("unicode_escape").decode("utf-8")
        # self._logger.debug(f"raw resp: <<{raw}>>")
        # Check that we got our command back
        if not resp.startswith(cmd):
            raise RuntimeError("Could not send command")
        # 2, because of \r\n
        return resp[len(cmd) + 2 :]

    async def _run(self, task_status: TaskStatus) -> None:
        """Parse input from this serial console.

        Put data in `_responses` whenever the prompt is found in the input.

        The implementation is not optimized at all. It will hog the CPU while it
        continuously polls for data. It is certainly not meant for applications
        with limited resources.
        """
        # Early out
        if self._prompt is None:
            await checkpoint()
            raise RuntimeError("You must specify the prompt first")
        async with AsyncExitStack() as stack:
            stack.enter_context(self._cancel_scope)
            await stack.enter_async_context(self._responses_send)
            logger_info = DelimitedBuffer(self._logger.info)
            stack.enter_context(logger_info)
            self._logger.info("Opening serial connection")
            # We call `Serial.open` in a worker thread since it may block the event
            # loop otherwise. In turn, this means that `Serial.__enter__` becomes a
            # no-op (which is what we want).
            await anyio.to_thread.run_sync(self._serial.open)
            stack.enter_context(self._serial)
            self._logger.info("Opened serial connection")
            task_status.started()

            buffer = ""
            while True:
                async with self._serial_lock:
                    # Ideally, there should be something like async_read so that
                    # we wouldn't have to continuously poll for data.
                    try:
                        raw_serial_data = self._serial.read(
                            self._serial.in_waiting
                        ).decode()
                    except UnicodeDecodeError:
                        self._logger.warning(
                            "Could not decode data from console. Skipping said data."
                        )
                        continue
                    if raw_serial_data:
                        logger_info.on_next(raw_serial_data)
                    # The raw serial data may contain partial responses. Therefore,
                    # we buffer it until we can recognize the prompt in it.
                    buffer += raw_serial_data
                    assert self._prompt is not None
                    if self._prompt in buffer:
                        # Split the buffer into individual responses (separated by
                        # the prompt).
                        responses = buffer.split(self._prompt)
                        # Note that `"x".split("x")` returns ["", ""]. Consequently,
                        # there are at least two responses in the buffer.
                        assert len(responses) >= 2
                        # Put all responses in the queue except for the last one.
                        for response in responses[:-1]:
                            # We're not afraid of `anyio.WouldBlock` since the response
                            # stream is not bounded (see [1]).
                            self._responses_send.send_nowait(response)
                        # The last response may be partial, so we re-initialize the
                        # buffer with it and wait until it is complete in a future
                        # iteration.
                        buffer = responses[-1]
                await anyio.sleep(0.01)

    async def __aenter__(self) -> Console:
        await self._tg.start(self._run)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._cancel_scope.cancel()
