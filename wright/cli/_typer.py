import logging
import sys
from functools import partial
from pathlib import Path
from typing import Optional
from enum import unique, Enum

import anyio
import typer

from .. import commands, config
from ..device import Device, DeviceDescription, DeviceType
from ..device.models import Branding
from ..device.execution_context import WrightLiveLinux, enter_context
from ._log_format import CliFormatter
from ..relay_lib_seeed import relay_on, relay_off

app = typer.Typer()

_HANDLER = logging.StreamHandler(stream=sys.stdout)
_HANDLER.setLevel(logging.DEBUG)
_HANDLER.setFormatter(CliFormatter())

_LOGGER = logging.getLogger()  # root logger
_LOGGER.addHandler(_HANDLER)
_LOGGER.setLevel(logging.DEBUG)


# TODO: Replace with `Literal` when typer supports it
@unique
class Power(Enum):
    ON = "on"
    OFF = "off"


@app.command()
def turn_power(
    power: Power = typer.Argument(...), relay_number: int = typer.Argument(default=1)
):
    """Set the power on or off on the device"""
    if power == Power.ON:
        relay_on(relay_number)
    elif power == Power.OFF:
        relay_off(relay_number)


@app.command()
def create_config_image(
    dest: Path = typer.Argument(..., writable=True),
    device_type: DeviceType = typer.Option(..., envvar="WRIGHT_DEVICE_TYPE"),
    device_version: str = typer.Option(..., envvar="WRIGHT_DEVICE_VERSION"),
    branding: Branding = typer.Option(..., envvar="WRIGHT_BRANDING"),
    hostname: str = typer.Option(..., envvar="WRIGHT_HOSTNAME"),
    pcb_identification_number: str = typer.Option(
        ..., envvar="WRIGHT_PCB_IDENTIFICATION_NUMBER"
    ),
) -> None:
    """Create config image as used in the reset-device command."""
    command = partial(
        config.create_config_image,
        dest,
        device_type=device_type,
        device_version=device_version,
        branding=branding,
        hostname=hostname,
        pcb_identification_number=pcb_identification_number,
    )
    anyio.run(command)


@app.command()
def reset_device(
    swu: Path = typer.Argument(..., exists=True, readable=True),
    *,
    device_type: DeviceType = typer.Option(..., envvar="WRIGHT_DEVICE_TYPE"),
    device_version: str = typer.Option(..., envvar="WRIGHT_DEVICE_VERSION"),
    branding: Branding = typer.Option(..., envvar="WRIGHT_BRANDING"),
    pcb_identification_number: str = typer.Option(
        None, envvar="WRIGHT_PCB_IDENTIFICATION_NUMBER"
    ),
    tty: Optional[Path] = typer.Option(None, envvar="WRIGHT_TTY"),
    jtag_usb_serial: Optional[str] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_SERIAL"
    ),
    jtag_usb_hub_location: Optional[str] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_HUB_LOCATION"
    ),
    jtag_usb_hub_port: Optional[int] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_HUB_PORT"
    ),
    skip_reset_firmware: bool = typer.Option(
        False, envvar="WRIGHT_SKIP_RESET_FIRMWARE"
    ),
) -> None:
    """Reset device to mint condition."""
    # Device description (translate CLI args)
    description = DeviceDescription.from_raw_args(
        device_type=device_type,
        device_version=device_version,
        pcb_identification_number=pcb_identification_number,
        tty=tty,
        jtag_usb_serial=jtag_usb_serial,
        jtag_usb_hub_location=jtag_usb_hub_location,
        jtag_usb_hub_port=jtag_usb_hub_port,
    )
    _LOGGER.info('Using TTY "%s"', description.link.communication.tty)
    # Command settings (translate CLI args)
    reset_firmware_settings = commands.StepSettings(not skip_reset_firmware)
    settings = commands.ResetDeviceSettings(reset_firmware_settings)
    # Run command
    command = partial(
        commands.reset_device,
        description,
        swu,
        branding,
        settings=settings,
        logger=_LOGGER,
    )
    anyio.run(command)


@app.command()
def run(
    command: str,
    *,
    device_type: DeviceType = typer.Option(..., envvar="WRIGHT_DEVICE_TYPE"),
    device_version: str = typer.Option(..., envvar="WRIGHT_DEVICE_VERSION"),
    tty: Optional[Path] = typer.Option(None, envvar="WRIGHT_TTY"),
    jtag_usb_serial: Optional[str] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_SERIAL"
    ),
    jtag_usb_hub_location: Optional[str] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_HUB_LOCATION"
    ),
    jtag_usb_hub_port: Optional[int] = typer.Option(
        None, envvar="WRIGHT_JTAG_USB_HUB_PORT"
    ),
    power_relay: Optional[int] = typer.Option(None, envvar="WRIGHT_POWER_RELAY"),
    boot_mode_gpio: Optional[int] = typer.Option(None, envvar="WRIGHT_BOOT_MODE_GPIO"),
) -> None:
    """Run the given command in Wright Live Linux."""
    # Device description (translate CLI args)
    description = DeviceDescription.from_raw_args(
        device_type=device_type,
        device_version=device_version,
        tty=tty,
        jtag_usb_serial=jtag_usb_serial,
        jtag_usb_hub_location=jtag_usb_hub_location,
        jtag_usb_hub_port=jtag_usb_hub_port,
        power_relay=power_relay,
        boot_mode_gpio=boot_mode_gpio,
    )
    device = Device.from_description(description)

    async def _boot() -> None:
        async with device, enter_context(WrightLiveLinux, device) as linux:
            await linux.run(command)

    anyio.run(_boot)


@app.command()
def gui() -> None:
    """Show the GUI."""
    # We import inside this function to avoid the dependency for the
    # CLI-only use case.
    from ..gui import gui as _gui  # pylint: disable=import-outside-toplevel

    _gui()
