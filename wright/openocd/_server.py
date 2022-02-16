from __future__ import annotations

import os
from logging import Logger, getLogger
from pathlib import Path
from subprocess import SubprocessError
from typing import Optional, Sequence

import anyio
from anyio.abc import TaskStatus

from ..subprocess import run_process

_LOGGER = getLogger(__name__)
_OPENOCD_EXE = os.environ.get("WRIGHT_OPENOCD_EXE", "openocd")


class ServerError(Exception):
    """General OpenOCD server error."""


async def run_server(
    config: Optional[Path] = None,
    commands: Optional[Sequence[str]] = None,
    *,
    debug: bool = False,
    task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
    logger: Optional[Logger] = None,
) -> None:
    """Run an OpenOCD server in the foreground."""
    # Fill in default arguments
    if commands is None:
        commands = []
    if logger is None:
        logger = _LOGGER
    # Translate the arguments of this function into the corresponding CLI arguments
    # for the OpenOCD server.
    args: list[str] = []
    if config is not None:
        args += ["--file", str(config)]
    for command in commands:
        args += ["--command", command]
    if debug:
        args.append("--debug")
    process_command = (_OPENOCD_EXE, *args)
    # When OpenOCD outputs the following, we consider the server "ready"
    ready_regex = r"Listening on port 3333 for gdb connections"
    # The OpenOCD process doesn't stop on error but simply logs the error instead.
    # We want it to stop on error. Therefore, we search the output and manually
    # stop the process when we find an error message.
    error_regex = r"Error: .*"
    # Start the server process
    try:
        await run_process(
            process_command,
            check_rc=False,
            stdout_logger=logger,
            error_regex=error_regex,
            ready_regex=ready_regex,
            task_status=task_status,
        )
    except SubprocessError as exc:
        raise ServerError(exc) from exc
