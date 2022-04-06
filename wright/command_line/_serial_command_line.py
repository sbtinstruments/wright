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

from ..util import DelimitedBuffer
from ._command_line import CommandLine

_LOGGER = logging.getLogger(__name__)


class SerialCommandLine(CommandLine):
    """Serial command line used to send commands to the device."""

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
    ) -> AsyncIterator[SerialCommandLine]:
        """Create a command line and run it in the background.

        This is a convenience method that creates a `TaskGroup` internally.
        """
        async with anyio.create_task_group() as tg:
            async with cls(tg, *args, **kwargs) as command_line:
                yield command_line

    async def force_prompt(self) -> None:
        """Force the prompt to appear.

        This is done by continuously spamming the command line with "echo".
        During boot, any message will halt the boot sequence
        and show the prompt.

        We use this during boot to interrupt the boot process and enter,
        e.g., the U-boot command line.
        """
        # Spam the serial line with simple "echo" commands.
        for i in itertools.count():  # Infinite range
            # Each command is unique (uses a different `i`) so that we
            # can distinguish them. Otherwise, the `run` call may mistake
            # a previous response as its own.
            try:
                # Use a small timeout so that we really do spam the
                # line and are able to interrupt a boot process.
                with anyio.fail_after(0.5):
                    resp = await self.run(f"echo {i}")
            except (RuntimeError, TimeoutError):
                # If the command fails we simply try again
                continue
            # If we get an invalid response, we try again.
            if resp != str(i):
                self._logger.debug(f'Invalid response: "{resp}" != {str(i)}')
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

    async def run(
        self,
        command: str,
        *,
        check_error_code: bool = True,
        strip_trailing_white_space: bool = True,
        **_: Any,
    ) -> str:
        """Run command and wait for the response."""
        await self.run_nowait(command)
        resp = await self.wait_for_prompt()
        # raw = resp.encode("unicode_escape").decode("utf-8")
        # self._logger.debug(f"raw resp: <<{raw}>>")
        # Check that we got our command back. Note that even though we submit
        # the command suffixed with a single "\n" (see [3]), we get it back
        # suffixed with "\r\n".
        returned_command = command + "\r\n"
        if not resp.startswith(returned_command):  # [2]
            raise RuntimeError("Could not send command")
        # Remove the returned command from the response
        resp = resp[len(returned_command) :]
        # Strip any trailing "new line" characters.
        #
        # Most commands output trailing new lines for formatting purposes.
        # I.e., to ensure that the prompt appears on a new line and not directly
        # after the output. This does not apply to all commands, however.
        # E.g., `cat` doesn't add a trailing new line character.
        #
        # Disable this feature with `strip_trailing_white_space` if you know the exact
        # output format of your command and rely on it. E.g., if you want to use `cat`
        # to check a file for trailing new line characters.
        if strip_trailing_white_space:
            resp = resp.rstrip("\r\n")
        # Early out
        if not check_error_code:
            return resp
        # Check error code via recursive call
        error_code = await self.run("echo $?", check_error_code=False)
        assert error_code is not None
        if error_code.strip() != "0":
            raise RuntimeError(f"Command failed with error code {error_code}")
        return resp

    async def run_nowait(self, command: str) -> None:
        """Run command but don't wait for a response."""
        if "\n" in command:
            # We don't allow end-line characters. I.e., we don't allow multi-line
            # commands. Said commands interfere with our error check at [2] and
            # the subsequent result parsing.
            raise ValueError("Command can't contain end-line characters.")
        # Note that `write_line ` adds an end-line character. In turn, this causes
        # the device to execute the given command.
        await self.write_line(command)

    async def write_line(self, text: str) -> None:
        """Write the given text (suffixed with an end-line character).

        If you want to run a command on the device, use `run` instead. The latter
        has optional error checks and result parsing.
        """
        async with self._serial_lock:
            self._serial.write((text + "\n").encode())  # [3]

    async def _run(self, task_status: TaskStatus) -> None:
        """Parse input from this command line.

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
                            "Could not decode data from command line. Skipping said data."
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

    async def __aenter__(self) -> SerialCommandLine:
        await self._tg.start(self._run)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._cancel_scope.cancel()
