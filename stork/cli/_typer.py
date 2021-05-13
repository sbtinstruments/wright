import logging
import sys
from pathlib import Path
from typing import Optional

import anyio
import typer

from .. import commands, config
from ..config.branding import Branding
from ..device import DeviceDescription, DeviceType
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
    device_type: DeviceType = typer.Option(..., envvar="STORK_DEVICE_TYPE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
) -> None:
    """Create config image as used in the reset-device command."""
    config.create_config_image(
        dest, device_type=device_type, branding=branding, hostname=hostname
    )


@app.command()
def reset_device(
    swu: Path = typer.Argument(..., exists=True, readable=True),
    *,
    device_type: DeviceType = typer.Option(..., envvar="STORK_DEVICE_TYPE"),
    branding: Branding = typer.Option(..., envvar="STORK_BRANDING"),
    hostname: str = typer.Option(..., envvar="STORK_HOSTNAME"),
    tty: Optional[Path] = typer.Option(None, envvar="STORK_TTY"),
    jtag_usb_serial: Optional[str] = typer.Option(None, envvar="STORK_JTAG_SERIAL"),
    skip_reset_firmware: bool = typer.Option(False, envvar="STORK_SKIP_RESET_FIRMWARE"),
) -> None:
    """Reset device to mint condition."""

    async def _reset_device() -> None:
        try:
            description = DeviceDescription.from_raw_args(
                device_type=device_type,
                hostname=hostname,
                tty=tty,
                jtag_usb_serial=jtag_usb_serial,
            )
            _LOGGER.info('Using TTY "%s"', description.link.communication.tty)
            await commands.reset_device(
                description,
                swu,
                branding,
                skip_reset_firmware=skip_reset_firmware,
                logger=_LOGGER,
            )
        except KeyboardInterrupt:
            _LOGGER.info("User interrupted the program")

    anyio.run(_reset_device)


@app.command()
def gui() -> None:
    """Show the GUI."""
    # We import inside this function to avoid the dependency for the
    # CLI-only use case.
    from ..gui import gui as _gui  # pylint: disable=import-outside-toplevel

    _gui()
