from typing import Any, Optional
from anyio.lowlevel import checkpoint
from anyio import move_on_after

from ....command_line import SerialCommandLine


async def force_log_in_over_serial(
    serial: SerialCommandLine,
    **kwargs: Any,
) -> None:
    """Force log in over the serial connection.

    Keeps trying until the log-in succeeds.
    """
    # Spam serial line until we see the log-in prompt
    old_prompt = serial._prompt
    serial._prompt = "login:"
    while True:
        await serial.write_line("")
        async with move_on_after(0.5):
            await serial.wait_for_prompt()
            break
    await log_in_over_serial(serial, **kwargs)
    serial._prompt = old_prompt


async def log_in_over_serial(
    serial: SerialCommandLine,
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Log in to the device over the serial connection."""
    noop = True
    if username is not None:
        await serial.write_line(username)
        noop = False
    if password is not None:
        await serial.write_line(password)
        noop = False
    # Checkpoint for the no-operation (noop) case
    if noop:
        await checkpoint()
