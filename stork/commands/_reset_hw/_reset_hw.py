import logging
import os
import shutil
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable, Optional
from contextlib import AsyncExitStack

from ...branding import Branding
from ...console import Console
from ...hardware import Hardware
from ...tftp import AsyncTFTPServer
from ...util import get_local_ip
from .._command import StepByStepCommand
from .._step import Instruction
from ._validation import raise_if_bad_hostname
from .subcommands import (boot_to_os, erase_data, install_firmware,
                          install_software, prepare_files)

_LOGGER = logging.getLogger(__name__)

TEMP_DIR = Path(f"/tmp/stork-{os.getpid()}")


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
    skip_system_image: Optional[bool] = None,
    skip_config_image: Optional[bool] = None,
) -> StepByStepCommand:
    start = datetime.now()
    _LOGGER.info(f'Using TTY "{tty}"')

    # Extra validation
    raise_if_bad_hostname(hostname, hardware)

    # Default arguments
    if tty is None:
        tty = Path("/dev/ttyUSB0")
    if tftp_host is None:
        tftp_host = get_local_ip()
    if tftp_port is None:
        tftp_port = 6969

    async with AsyncExitStack() as stack:
        # Set files up so that the command can run
        stack.callback(shutil.rmtree, TEMP_DIR)
        steps = prepare_files(
            TEMP_DIR, swu, hardware, branding, hostname, fsbl_elf, uboot_bin, output_cb
        )
        async for step in steps:
            yield step

        # TFTP server
        yield "Start TFTP server"
        tftp_server = AsyncTFTPServer(tftp_host, tftp_port)
        await stack.enter_async_context(tftp_server)

        # Console connection
        yield "Connect console"
        console = Console(
            Path(tty),
            hardware=hardware,
            hostname=hostname,
            output_cb=partial(output_cb, source="console"),
        )
        await stack.enter_async_context(console)

        # Install firmware
        if not skip_install_firmware:
            steps = install_firmware(console, hardware, tftp_host, tftp_port, output_cb)
            async for step in steps:
                yield step

        yield "Shut down hardware"
        await console.cmd("mango pmic shutdown", wait_for_prompt=False)

        yield Instruction(
            "Do the following:\n"
            "  1. Power off the hardware\n"
            "  2. Remove the 2-pin jumper\n"
            "  3. Power on the hardware"
        )
        await console.force_prompt()

        # Install software
        steps = install_software(
            console,
            hardware,
            tftp_host,
            tftp_port,
            skip_system_image,
            skip_config_image,
        )
        async for step in steps:
            yield step

        # Boot to operating system
        async for step in boot_to_os(console):
            yield step

        # Erase data
        async for step in erase_data(console):
            yield step

        yield "Power off hardware"
        await console.cmd("poweroff")

    end = datetime.now()
    delta = end - start
    yield f"Reset hardware successful (took {delta})"
