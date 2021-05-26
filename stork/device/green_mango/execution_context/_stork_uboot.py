from __future__ import annotations

from contextlib import AsyncExitStack
from importlib import resources
from logging import Logger
from typing import TYPE_CHECKING, Optional

import anyio
from anyio.abc import TaskGroup

from .... import openocd as ocd
from ....subprocess import run_process
from ....util import TEMP_DIR
from ... import assets
from ..._device_description import DeviceCommunication
from ...control.boot_mode import BootMode
from ._uboot import Uboot

if TYPE_CHECKING:
    from .._green_mango import GreenMango

_CFG_FILE = TEMP_DIR / "green_mango.cfg"
_FSBL_FILE = TEMP_DIR / "fsbl.elf"
_UBOOT_FILE = TEMP_DIR / "u-boot.bin"


class StorkUboot(Uboot):
    """Stork's built-in version of U-boot.

    This does not rely in an existing U-boot installation on the device (in
    contrast to `Uboot`).
    """

    def __init__(self, device: "GreenMango", tg: TaskGroup) -> None:
        # The built-in U-boot is based on the "bactobox" defconfig. Therefore,
        # the hostname is "bactobox". It works fine on, e.g., a Zeus device as
        # well.
        # TODO: Change hostname of built-in U-boot to something generic like
        # "green mango".
        prompt = f"\r\nbactobox> "
        super().__init__(device, tg, prompt)

    async def _boot(self) -> None:
        with self._dev.scoped_boot_mode(BootMode.JTAG):
            await self._dev.hard_restart()
            # The Zynq chip does its boot mode check within the first 100 ms.
            # Therefore, we wait 100 ms before we switch back to the default
            # boot mode.
            await anyio.sleep(0.1)
        await jtag_boot_to_uboot(self._dev)


async def jtag_boot_to_uboot(device: "GreenMango") -> None:
    """Boot directly to U-boot via JTAG."""
    _extract_files(logger=device.logger)

    async with AsyncExitStack() as stack:
        # OCD server
        device.logger.info("Start OpenOCD server")
        try:
            await _start_server(stack, device.link.communication, logger=device.logger)
        except ocd.ServerError:
            device.logger.warning(
                "Could not start OpenOCD server. We power cycle the "
                "USB port to reset the JTAG cable. Usually, this fixes the issues."
            )
            # Cycle power to USB ports
            await _power_cycle_usb_ports(logger=device.logger.getChild("usb"))
            # Try to start the server once more.
            # TODO: Somehow add the time that it takes to do this "unexpected" extra step
            # to the overall timeout.
            device.logger.info("Start the OpenOCD server once more.")
            await _start_server(stack, device.link.communication, logger=device.logger)

        # OCD client
        device.logger.info("Connect OpenOCD client")
        ocd_client = ocd.Client(logger=device.logger.getChild("ocd.client"))
        await stack.enter_async_context(ocd_client)

        # Low-level OCD control
        device.logger.info("Reset and halt CPU")
        await ocd_client.cmd("reset halt")
        device.logger.info("Copy FSBL to device memory")
        await ocd_client.cmd(f"load_image {_FSBL_FILE} 0 elf")
        device.logger.info("Execute FSBL")
        await ocd_client.cmd("resume 0")
        await ocd_client.cmd("sleep 4000")
        device.logger.info("Copy U-boot to device memory")
        await ocd_client.cmd("halt")
        await ocd_client.cmd(f"load_image {_UBOOT_FILE} 0x04000000 bin")

        # TODO: Call `Console.force_prompt` before we resume
        device.logger.info("Execute U-boot")
        await ocd_client.cmd("resume 0x04000000")


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
    stack: AsyncExitStack, communication: DeviceCommunication, *, logger: Logger
) -> None:
    # Commands that we run when the server runs
    commands: list[str] = []
    if communication.jtag_usb_serial is not None:
        commands.append(f"ftdi_serial {communication.jtag_usb_serial}")
    # Run the server
    ocd_server = ocd.run_server_in_background(
        _CFG_FILE, commands, logger=logger.getChild("ocd.server")
    )
    await stack.enter_async_context(ocd_server)


async def _power_cycle_usb_ports(*, logger: Optional[Logger] = None) -> None:
    command = "uhubctl", "--ports", "1", "--action", "cycle"
    await run_process(command, check_rc=True, stdout_logger=logger)
    # Wait a moment for the USB devices to set themselves up
    await anyio.sleep(2)
