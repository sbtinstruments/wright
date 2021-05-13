from __future__ import annotations

import os
from contextlib import asynccontextmanager
from logging import Logger, getLogger
from pathlib import Path
from typing import Any, AsyncIterator, Optional, Sequence

import anyio

from ..subprocess import run_process

_LOGGER = getLogger(__name__)
_OPENOCD_EXE = os.environ.get("STORK_OPENOCD_EXE", "openocd")


@asynccontextmanager
async def run_server_in_background(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    """Run an OpenOCD server in the background.

    Automatically stops the server when you exit the scope.

    This is a convenience function that calls `run_server` internally.
    """

    async def _wrapper() -> None:
        await run_server(*args, **kwargs)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_wrapper)
        # Wait until the server is ready
        # TODO: Listen to server output and wait until we see a "ready" message.
        # E.g., the "Listening on port 3333 for gdb connections" message.
        # The current `sleep(2)` approach is a bit crude.
        await anyio.sleep(2)
        try:
            yield
        finally:
            tg.cancel_scope.cancel()


async def run_server(
    config: Optional[Path] = None,
    commands: Optional[Sequence[str]] = None,
    *,
    debug: bool = False,
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
    # Start the server process
    await run_process(process_command, check_rc=False, stdout_logger=logger)
