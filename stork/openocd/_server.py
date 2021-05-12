from __future__ import annotations

import os
from contextlib import asynccontextmanager
from importlib import resources
from logging import Logger, getLogger
from typing import Any, AsyncIterator, Optional

import anyio

from ..subprocess import run_process
from ..util import TEMP_DIR
from . import configs

_LOGGER = getLogger(__name__)

_OPENOCD_EXE = os.environ.get("STORK_OPENOCD_EXE", "openocd")
_CFG_FILE = TEMP_DIR / "green_mango.cfg"


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


async def run_server(debug: bool = False, logger: Optional[Logger] = None) -> None:
    """Run an OpenOCD server in the foreground."""
    # Fill in default arguments
    if logger is None:
        logger = _LOGGER
    logger.info("Extract the OpenOCD config file from the Python package")
    _extract_config_file()
    # Translate the arguments of this function into the corresponding CLI arguments
    # for the OpenOCD server.
    args = ["-f", str(_CFG_FILE)]
    if debug:
        args.append("-d3")
    command = (_OPENOCD_EXE, *args)
    # Start the server process
    await run_process(command, check_rc=False, stdout_logger=logger)


def _extract_config_file() -> None:
    _CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg_data = resources.read_binary(configs, _CFG_FILE.name)
    _CFG_FILE.write_bytes(cfg_data)
