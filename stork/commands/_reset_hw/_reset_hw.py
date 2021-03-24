import logging
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ...branding import Branding
from ...command import StepByStepCommand
from ...hardware import (
    BoardDefinition,
    GreenMango,
    Hardware,
    RelayBootModeControl,
    RelayPowerControl,
)
from ...tftp import AsyncTFTPServer
from .subcommands import prepare_files

_LOGGER = logging.getLogger(__name__)

TEMP_DIR = Path(f"/tmp/stork")


async def reset_hw(
    swu: Path,
    *,
    hardware: Hardware,
    branding: Branding,
    hostname: str,
    fsbl_elf: Path,
    uboot_bin: Path,
    tty: Optional[Path] = None,
    tftp_host: Optional[str] = None,
    tftp_port: Optional[int] = None,
    output_cb: Optional[Callable[[str], None]] = None,
    skip_install_firmware: Optional[bool] = None,
) -> StepByStepCommand:
    start = datetime.now()

    # Board definition
    board_definition = BoardDefinition.with_defaults(
        hardware=hardware,
        power_control=RelayPowerControl(1),
        boot_mode_control=RelayBootModeControl(4),
        hostname=hostname,
        tty=tty,
        tftp_host=tftp_host,
        tftp_port=tftp_port,
    )

    _LOGGER.info(f'Using TTY "{board_definition.tty}"')

    async with AsyncExitStack() as stack:
        # Set files up so that the command can run
        steps = prepare_files(
            TEMP_DIR, swu, hardware, branding, hostname, fsbl_elf, uboot_bin, output_cb
        )
        async for step in steps:
            yield step

        # TFTP server
        yield "Start TFTP server"
        tftp_server = AsyncTFTPServer(
            board_definition.tftp_host, board_definition.tftp_port
        )
        await stack.enter_async_context(tftp_server)

        # Board
        board = GreenMango(board_definition, output_cb=output_cb)
        await stack.enter_async_context(board)

        # Install firmware
        if not skip_install_firmware:
            async for step in board.commands.install_firmware():
                yield step

        # Install software
        async for step in board.commands.install_software():
            yield step

        # Erase data
        async for step in board.commands.erase_data():
            yield step

    end = datetime.now()
    delta = end - start
    yield f"Reset hardware successful (took {delta})"
