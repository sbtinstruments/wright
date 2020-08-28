import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional

import typer

from ..hardware import Hardware
from ..branding import Branding
from ..reset import _reset_hw
from ..util import extract_swu, get_local_ip
from ._validation import raise_if_bad_hostname
from ..config import create_config_image

app = typer.Typer()

# TEMP_DIR = Path("/tmp/stork")
TEMP_DIR = Path(f"/tmp/stork-{os.getpid()}")
_LOGGER = logging.getLogger(__name__)


@app.command()
def reset_hw(
    swu: Path = typer.Argument(..., exists=True, readable=True),
    *,
    hardware: Hardware = typer.Option(..., envvar="STORK_HARDWARE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
    fsbl_elf: Path = typer.Option(..., exists=True, readable=True, envvar="STORK_FSBL_ELF"),
    tty: Path = typer.Option(
        Path("/dev/ttyUSB0"), exists=True, readable=True, writable=True, envvar="STORK_TTY"
    ),
    tftp_host: Optional[str] = typer.Option(None, envvar="STORK_TFTP_HOST"),
    tftp_port: Optional[int] = typer.Option(6969, envvar="STORK_TFTP_PORT"),
    skip_program_flash: bool = typer.Option(False, envvar="STORK_SKIP_PROGRAM_FLASH"),
    skip_system_image: bool = typer.Option(False, envvar="STORK_SKIP_SYSTEM_IMAGE"),
    skip_config_image: bool = typer.Option(False, envvar="STORK_SKIP_CONFIG_IMAGE"),
    restore_default_uboot_env: bool = typer.Option(False, envvar="STORK_RESTORE_DEFAULT_UBOOT_ENV"),
):
    # Extra validation
    raise_if_bad_hostname(hostname, hardware)
    # Default arguments
    if tftp_host is None:
        tftp_host = get_local_ip()

    # Copy over files to the temporary dir and switch to said dir
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(swu, TEMP_DIR)
    # Copy over the first-stage boot loader (FSBL).
    #
    # Note that this is NOT the FSBL that will end up on the board.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the board over JTAG.
    shutil.copy(fsbl_elf, TEMP_DIR / "fsbl.elf")
    os.chdir(TEMP_DIR)
    # Extract SWU contents. We will need it for later.
    extract_swu(Path(swu.name))
    # Create config image
    create_config_image(hardware=hardware, branding=branding, hostname=hostname)

    # Run command
    try:
        asyncio.run(
            _reset_hw(
                swu,
                hardware=hardware,
                hostname=hostname,
                tty=tty,
                tftp_host=tftp_host,
                tftp_port=tftp_port,
                skip_program_flash=skip_program_flash,
                skip_system_image=skip_system_image,
                skip_config_image=skip_config_image,
                restore_default_uboot_env=restore_default_uboot_env,
            )
        )
    except KeyboardInterrupt:
        _LOGGER.info("User interrupted the program")
    finally:
        shutil.rmtree(TEMP_DIR)


# Add a second command so that typer forces users to explicitly
# write out the commands.
@app.command()
def _ignore():
    pass
