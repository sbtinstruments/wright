from __future__ import annotations

import re
from contextlib import suppress
from logging import Logger
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, SubprocessError
from typing import Any, Optional, Pattern, Sequence, Union

import anyio
from anyio.abc import Process, TaskStatus
from anyio.streams.file import FileReadStream
from anyio.streams.text import TextReceiveStream

from ..util import DelimitedBuffer


async def run_process(
    command: Union[str, Sequence[str]],
    *,
    stdin_file: Optional[Path] = None,
    stdout_logger: Optional[Logger] = None,
    check_rc: Optional[bool] = None,
    error_regex: Optional[str] = None,
    ready_regex: Optional[str] = None,
    task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
    **kwargs: Any,
) -> None:
    """Run the given command as a process."""
    process: Optional[Process] = None
    try:
        process = await anyio.open_process(command, stderr=STDOUT, **kwargs)
        await _drain_streams(
            process,
            stdin_file=stdin_file,
            stdout_logger=stdout_logger,
            error_regex=error_regex,
            ready_regex=ready_regex,
            task_status=task_status,
        )
    except BaseException:
        if process is not None:
            # Try to gracefully terminate the process
            process.terminate()
            # Give the process some time to stop.
            #
            # Note that some processes may give some final output when they
            # receive a signal. E.g., "The user interrupted the program" on SIGTERM.
            # Therefore, this is also an opportunity to catch this final output
            # before we close the streams at [2].
            # If we don't do this, we get some nasty `AssertionError`s from
            # deep within asyncio about "feed_data after feed_eof". This is
            # because we close the stream (at [2]) while there is still some
            # finaly output from the process in flux.
            #
            # Shield this, because the parent task may be cancelled (and if this
            # is the case, the `_drain_streams` call will fail immediately without
            # shielding).
            with anyio.move_on_after(5, shield=True):  # [1]
                await _drain_streams(process, stdout_logger=stdout_logger)
        raise
    finally:
        if process is not None:
            # If the process already stopped (gracefully), this does nothing.
            # Otherwise, it kills the process for good.
            with suppress(ProcessLookupError):
                process.kill()
            # Close the streams (stdin, stdout, and stderr). Shield this for the same
            # reason as given for [1].
            with anyio.CancelScope(shield=True):
                await process.aclose()  # [2]

    assert process is not None
    assert process.returncode is not None
    # Check the return code (rc)
    if check_rc and process.returncode != 0:
        raise CalledProcessError(process.returncode, command)


async def _drain_streams(
    process: Process,
    *,
    stdin_file: Optional[Path] = None,
    stdout_logger: Optional[Logger] = None,
    error_regex: Optional[str] = None,
    ready_regex: Optional[str] = None,
    task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
) -> None:
    async with anyio.create_task_group() as tg:
        if process.stdin is not None and stdin_file is not None:
            tg.start_soon(_send_to_stdin, process, stdin_file)
        if process.stdout is not None and stdout_logger is not None:
            tg.start_soon(
                _receive_from_stdout,
                process,
                stdout_logger,
                error_regex,
                ready_regex,
                task_status,
            )
        # Wait for the process to exit normally
        await process.wait()


async def _send_to_stdin(process: Process, stdin_file: Path) -> None:
    assert process.stdin is not None
    # Forward data from file to stdin
    async with await FileReadStream.from_path(stdin_file) as chunks:
        async for chunk in chunks:
            await process.stdin.send(chunk)


async def _receive_from_stdout(
    process: Process,
    stdout_logger: Logger,
    error_regex: Optional[str] = None,
    ready_regex: Optional[str] = None,
    task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
) -> None:
    assert process.stdout is not None
    # Compile regex
    error_pattern: Optional[Pattern[str]] = None
    if error_regex is not None:
        error_pattern = re.compile(error_regex)
    ready_pattern: Optional[Pattern[str]] = None
    if ready_regex is not None:
        ready_pattern = re.compile(ready_regex)
    # Forward data from stdout to logger
    with DelimitedBuffer(stdout_logger.info) as logger_info:
        stream = TextReceiveStream(process.stdout)
        async for string in stream:  # pylint: disable=not-an-iterable
            logger_info.on_next(string)
            # Raise an error if the output matches the given regex (if any)
            # TODO: `string` may not necessarily split cleanly at newlines.
            # Use `DelimitedBuffer` or similar to get around this.
            if error_pattern is not None and error_pattern.search(string):
                raise SubprocessError(string)
            if ready_pattern is not None and ready_pattern.search(string):
                task_status.started()
