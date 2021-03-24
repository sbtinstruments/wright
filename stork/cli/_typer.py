import asyncio
from functools import partial
import logging
from pathlib import Path
from typing import Dict, Optional

import typer

from .. import commands
from ..command import steps as command_steps
from ..branding import Branding
from ..config import create_config_image as cfi
from ..hardware import Hardware
from ..logger import OutputLogger

app = typer.Typer()


_LOGGER = logging.getLogger(__name__)


@app.command()
def create_config_image(
    hardware: Hardware = typer.Option(..., envvar="STORK_HARDWARE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
):
    cfi(hardware=hardware, branding=branding, hostname=hostname)


@app.command()
def reset_hw(
    swu: Path = typer.Argument(..., exists=True, readable=True),
    *,
    hardware: Hardware = typer.Option(..., envvar="STORK_HARDWARE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
    fsbl_elf: Path = typer.Option(
        ..., exists=True, readable=True, envvar="STORK_FSBL_ELF"
    ),
    uboot_bin: Path = typer.Option(
        ..., exists=True, readable=True, envvar="STORK_UBOOT_BIN"
    ),
    tty: Optional[Path] = typer.Option(None, envvar="STORK_TTY"),
    tftp_host: Optional[str] = typer.Option(None, envvar="STORK_TFTP_HOST"),
    tftp_port: Optional[int] = typer.Option(6969, envvar="STORK_TFTP_PORT"),
    skip_install_firmware: bool = typer.Option(
        False, envvar="STORK_SKIP_INSTALL_FIRMWARE"
    ),
):
    async def _reset_hw():
        try:
            with OutputLogger() as output_logger:
                steps = commands.reset_hw(
                    swu,
                    hardware=hardware,
                    branding=branding,
                    hostname=hostname,
                    fsbl_elf=fsbl_elf,
                    uboot_bin=uboot_bin,
                    output_cb=output_logger.log,
                    tty=tty,
                    tftp_host=tftp_host,
                    tftp_port=tftp_port,
                    skip_install_firmware=skip_install_firmware,
                )
                async for step in steps:
                    if isinstance(step, command_steps.StatusUpdate):
                        print_info(step)
                    elif isinstance(step, command_steps.Instruction):
                        print_instruction(step.text)
                    elif isinstance(step, command_steps.RequestConfirmation):
                        print_instruction(step.text)
                        press_enter_to_continue()
                    else:
                        raise RuntimeError("Unknown output")
        except KeyboardInterrupt:
            _LOGGER.info("User interrupted the program")

    asyncio.run(_reset_hw())


def print_info(text):
    print("\033[7m>>> " + text + "\033[0m")


def print_instruction(text):
    print("\033[44m>>> " + text + "\033[0m")


def press_enter_to_continue():
    print_instruction("Press <Enter> to continue")
    input()


@app.command()
def gui():
    from ..gui import gui

    gui()
