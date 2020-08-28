import asyncio
import itertools
import logging
from pathlib import Path
from typing import Optional

import serial

_LOGGER = logging.getLogger(__name__)


class Board:
    def __init__(self, tty: Path, prompt: str):
        baud_rate = 115200
        self.serial = serial.Serial(str(tty), baud_rate)
        self._read_task = None
        self.prompt = prompt
        self._responses = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def force_prompt(self):
        """Force the prompt to appear.

        This is done by continuously spamming the board via the serial
        connection. During boot, any message will halt the boot sequence
        and show the prompt.

        We use this during boot to interript the boot process and enter,
        e.g., the U-boot console.
        """
        # Spam the serial line with simple "echo" commands.
        for i in itertools.count():  # Infinite range
            # Each command is unique (uses a different `i`) so that we
            # can distinguish them. Otherwise, the `cmd` call may mistake
            # a previous result as its own.
            cmd = self.cmd(f"echo {i}")
            try:
                # Use a small timeout so that we really do spam the
                # line and are able to interrupt a boot process.
                resp = await asyncio.wait_for(cmd, 0.1)
            except (RuntimeError, asyncio.TimeoutError):
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

        Return the last response seen in the serial output. That is, the
        output since the last `prompt` occurred.
        """
        # Wait for a response. Whenever the prompt appears in the serial
        # output, a response will be emitted.
        result = await self._responses.get()
        # Sometimes, there may be multiple responses. E.g., when we spam
        # the serial line in an attempt to interrupt a boot process.
        #
        # We overcome this situation by simply emptying the entire queue
        # and returning the last element. This discards all other elements
        # in the queue.
        while self._responses.qsize() > 0:
            try:
                result = self._responses.get_nowait()
            except asyncio.QueueEmpty:
                break
        return result

    async def cmd(
        self, cmd, *, wait_for_prompt=True, check_error_code=True
    ) -> Optional[str]:
        resp = await self._cmd(cmd, wait_for_prompt=wait_for_prompt)
        # Early out
        if not wait_for_prompt or not check_error_code:
            return resp
        # Check error code
        error_code = await self._cmd("echo $?")
        if error_code.strip() != "0":
            raise RuntimeError(f"Command failed with error code {error_code}")
        return resp

    async def _cmd(self, cmd, *, wait_for_prompt=True) -> Optional[str]:
        async with self._lock:
            # Add line end so that the command is executed
            self.serial.write((cmd + "\n").encode())
        # Early out
        if not wait_for_prompt:
            return
        resp = await self.wait_for_prompt()
        # raw = resp.encode("unicode_escape").decode("utf-8")
        # _LOGGER.debug(f"raw resp: <<{raw}>>")
        # Check that we got our command back
        if not resp.startswith(cmd):
            raise RuntimeError("Could not send command")
        # 2, because of \r\n
        return resp[len(cmd) + 2 :]

    async def reset(self):
        """Send 'reset' command but do not wait for acknowledgement"""
        await self.cmd("reset", wait_for_prompt=False)

    async def _parse_serial_output(self):
        """Put data in `_responses` whenever `prompt` is found in the input.

        The implementation is not optimized at all. It will hog the CPU while it
        continuously polls for data. It is certainly not meant for applications
        with limited resources.
        """
        buffer = ""
        while True:
            async with self._lock:
                # Ideally, there should be something like async_read so that
                # we wouldn't have to continuously poll for data.
                try:
                    raw_serial_data = self.serial.read(self.serial.in_waiting).decode()
                except UnicodeDecodeError:
                    _LOGGER.warning(
                        "Could not decode data from board. Skipping said data."
                    )
                print(raw_serial_data, end="", flush=True)
                # The raw serial data may contain partial responses. Therefore, we buffer
                # it until we can recognize `prompt` in it.
                buffer += raw_serial_data
                if self.prompt in buffer:
                    # Split the buffer into individual responses (separated by the prompt).
                    responses = buffer.split(self.prompt)
                    # Note that `"x".split("x")` returns ["", ""]. There, there should
                    # always be at least two responses in the buffer.
                    assert len(responses) >= 2
                    # Put all responses in the queue except for the last one.
                    for response in responses[:-1]:
                        await self._responses.put(response)
                    # The last response may be partial, so we re-initialize the
                    # buffer with it and wait until it is complete in a future
                    # iteration.
                    buffer = responses[-1]
            await asyncio.sleep(0.01)

    async def __aenter__(self):
        self.serial.__enter__()
        self._read_task = asyncio.create_task(self._parse_serial_output())
        return self

    async def __aexit__(self, *args):
        self._read_task.cancel()
        self.serial.__exit__()
