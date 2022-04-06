from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import resources
from logging import Logger
from typing import TYPE_CHECKING, AsyncIterator, Optional

import anyio
from anyio.abc import TaskStatus

from .... import openocd as ocd
from ....command_line import SerialCommandLine
from ....subprocess import run_process
from ....util import TEMP_DIR
from ... import assets
from ...control.boot_mode import BootMode
from ._uboot import Uboot

if TYPE_CHECKING:
    from ..._device import Device
    from ..._device_description import DeviceCommunication

_CFG_FILE = TEMP_DIR / "green_mango.cfg"
_FSBL_FILE = TEMP_DIR / "fsbl.elf"
_UBOOT_FILE = TEMP_DIR / "u-boot.bin"


class WrightLiveUboot(Uboot):
    """Live, tiny, and low-level execution context.

    Live, in the sense that:
     1. It lives entirely in device memory
     2. It is from an external source and not from the device itself

    Point (2) above is key. Basically, this means that this execution context doesn't
    depend on the device state. In other words, it's independent of the firmware
    installed on the device (if any).

    This is ideal for, e.g., an unused board that comes straight from the manufacturer.
    """

    async def _boot(self) -> None:
        with self.device.scoped_boot_mode(BootMode.JTAG):
            await self.device.hard_restart()
            # The Zynq chip does its boot mode check within the first 100 ms.
            # Therefore, we wait 100 ms before we switch back to the default
            # boot mode.
            await anyio.sleep(0.1)
        await jtag_boot_to_uboot(self.device)

    @asynccontextmanager
    async def _serial_cm(self) -> AsyncIterator[SerialCommandLine]:
        # The built-in U-boot is based on the "bactobox" defconfig. Therefore,
        # the hostname is "bactobox". It works fine on, e.g., a Zeus device as
        # well.
        # TODO: Change hostname of built-in U-boot to something generic like
        # "green mango".
        prompt = "bactobox> "
        async with self._create_serial(prompt) as serial:
            # Spam 'echo' commands until the serial prompt appears
            with anyio.fail_after(5):
                await serial.force_prompt()
            yield serial


async def jtag_boot_to_uboot(device: "Device") -> None:
    """Boot directly to U-boot via JTAG."""
    _extract_files(logger=device.logger)

    async with anyio.create_task_group() as tg:
        # OCD server
        device.logger.info("Start OpenOCD server")
        try:
            await tg.start(_start_server, device.link.communication, device.logger)
        except ocd.ServerError:
            device.logger.warning("Could not start OpenOCD server.")
            # Early out if we don't have enough info to cycle power to the USB port
            if device.link.communication.jtag_usb_serial is None:
                device.logger.warning(
                    "At this point, we usually try to cycle power to the USB port "
                    "to reset the JTAG cable. We can't do this now, since we don't "
                    "have the JTAG cable serial number."
                )
                raise
            # Cycle power to USB ports
            device.logger.info(
                "We power cycle the USB port to reset the JTAG cable. "
                "Usually, this fixes the issues."
            )
            await _power_cycle_usb_ports(
                logger=device.logger.getChild("usb"),
                search=device.link.communication.jtag_usb_serial,
            )
            # Try to start the server once more.
            # TODO: Somehow add the time that it takes to do this "unexpected" extra
            # step to the overall timeout.
            device.logger.info("Start the OpenOCD server once more.")
            await tg.start(_start_server, device.link.communication, device.logger)

        # OCD client
        device.logger.info("Connect OpenOCD client")
        client_logger = device.logger.getChild("ocd.client")
        client_port = device.link.communication.ocd_tcl_port
        async with ocd.Client(port=client_port, logger=client_logger) as ocd_client:
            # Low-level OCD control
            device.logger.info("Reset and halt CPU")
            await ocd_client.run("reset halt")
            device.logger.info("Copy FSBL to device memory")
            await ocd_client.run(f"load_image {_FSBL_FILE} 0 elf")
            device.logger.info("Execute FSBL")
            await ocd_client.run("resume 0")
            await ocd_client.run("sleep 4000")
            device.logger.info("Copy U-boot to device memory")
            await ocd_client.run("halt")
            await ocd_client.run(f"load_image {_UBOOT_FILE} 0x04000000 bin")

            # TODO: Call `Console.force_prompt` before we resume
            device.logger.info("Execute U-boot")
            await ocd_client.run("resume 0x04000000")

        # Stop the server
        tg.cancel_scope.cancel()


def _extract_files(*, logger: Logger) -> None:
    # FSBL
    #
    # Note that this is NOT the FSBL that will end up on the device.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the device over JTAG.
    logger.info("Extract FSBL from Python package")
    fsbl_data = resources.read_binary(assets, _FSBL_FILE.name)
    _FSBL_FILE.write_bytes(fsbl_data)

    # U-boot
    #
    # Like with the FSBL, this is NOT the U-boot that ends up on the device.
    logger.info("Extract U-boot from Python package")
    uboot_data = resources.read_binary(assets, _UBOOT_FILE.name)
    _UBOOT_FILE.write_bytes(uboot_data)

    # OpenOCD config file
    logger.info("Extract OpenOCD config file from Python package")
    cfg_data = resources.read_binary(assets, _CFG_FILE.name)
    _CFG_FILE.write_bytes(cfg_data)


async def _start_server(
    communication: "DeviceCommunication",
    logger: Logger,
    *,
    task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
) -> None:
    # Commands that we run when the server runs
    commands: list[str] = []
    if communication.jtag_usb_serial is not None:
        logger.info(
            f'Use the FTDI device with serial number: "{communication.jtag_usb_serial}"'
        )
        commands.append(f"ftdi_serial {communication.jtag_usb_serial}")
    else:
        logger.info(
            "Use an arbitrary FTDI device (no specific serial number specified)"
        )
    if communication.ocd_tcl_port is not None:
        logger.info(f'Use TCL port number: "{communication.ocd_tcl_port}"')
        commands.append(f"tcl_port {communication.ocd_tcl_port}")
    else:
        logger.info("Use default TCL port number (no specific port number specified)")
    # Run the server
    await ocd.run_server(
        _CFG_FILE,
        commands,
        task_status=task_status,
        logger=logger.getChild("ocd.server"),
    )


async def _power_cycle_usb_ports(
    *,
    logger: Optional[Logger] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
) -> None:
    command = ["uhubctl", "--action", "cycle"]
    if location is not None:
        command += ("--location", location)
    if search is not None:
        command += ("--search", search)
    await run_process(command, check_rc=True, stdout_logger=logger)
    # Wait a moment for the USB devices to set themselves up
    await anyio.sleep(2)
