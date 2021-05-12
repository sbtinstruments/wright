import logging
import sys
from pathlib import Path
from typing import Optional

import anyio
import typer

from .. import commands, config
from ..branding import Branding
from ..hardware import Hardware
from ._log_format import CliFormatter

app = typer.Typer()

_HANDLER = logging.StreamHandler(stream=sys.stdout)
_HANDLER.setLevel(logging.DEBUG)
_HANDLER.setFormatter(CliFormatter())

_LOGGER = logging.getLogger()  # root logger
_LOGGER.addHandler(_HANDLER)
_LOGGER.setLevel(logging.DEBUG)


@app.command()
def create_config_image(
    dest: Path = typer.Argument(..., writable=True),
    hardware: Hardware = typer.Option(..., envvar="STORK_HARDWARE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
) -> None:
    """Create config image as used in the reset-hw command."""
    config.create_config_image(
        dest, hardware=hardware, branding=branding, hostname=hostname
    )


@app.command()
def reset_hw(
    swu: Path = typer.Argument(..., exists=True, readable=True),
    *,
    hardware: Hardware = typer.Option(..., envvar="STORK_HARDWARE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
    tty: Optional[Path] = typer.Option(None, envvar="STORK_TTY"),
    tftp_host: Optional[str] = typer.Option(None, envvar="STORK_TFTP_HOST"),
    tftp_port: Optional[int] = typer.Option(6969, envvar="STORK_TFTP_PORT"),
    skip_install_firmware: bool = typer.Option(
        False, envvar="STORK_SKIP_INSTALL_FIRMWARE"
    ),
) -> None:
    """Reset hardware to mint condition."""

    async def _reset_hw() -> None:
        try:
            await commands.reset_hw(
                swu,
                hardware=hardware,
                branding=branding,
                hostname=hostname,
                logger=_LOGGER,
                tty=tty,
                tftp_host=tftp_host,
                tftp_port=tftp_port,
                skip_install_firmware=skip_install_firmware,
            )
        except KeyboardInterrupt:
            _LOGGER.info("User interrupted the program")

    anyio.run(_reset_hw)


@app.command()
def gui() -> None:
    """Show the GUI."""
    # We import inside this function to avoid the dependency for the
    # CLI-only use case.
    from ..gui import gui as _gui  # pylint: disable=import-outside-toplevel

    _gui()
