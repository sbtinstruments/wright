from __future__ import annotations

from contextlib import AsyncExitStack
from importlib import resources
from typing import TYPE_CHECKING

import anyio

from .... import openocd as ocd
from ....util import TEMP_DIR
from ..._boot_mode import BootMode
from .. import assets
from ._uboot import Uboot

if TYPE_CHECKING:
    from .._green_mango import GreenMango


_FSBL_FILE = TEMP_DIR / "fsbl.elf"
_UBOOT_FILE = TEMP_DIR / "u-boot.bin"


class StorkUboot(Uboot):
    """Stork's built-in version of U-boot.

    This does not rely in an existing U-boot installation on the device (in
    contrast to `Uboot`).
    """

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
    # FSBL
    #
    # Note that this is NOT the FSBL that will end up on the hardware.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the hardware over JTAG.
    device.logger.info("Extract FSBL from Python package")
    fsbl_data = resources.read_binary(assets, "fsbl.elf")
    _FSBL_FILE.write_bytes(fsbl_data)

    # U-boot
    #
    # Like with the FSBL, this is NOT the U-boot that ends up on the hardware.
    device.logger.info("Extract U-boot from Python package")
    uboot_data = resources.read_binary(assets, "u-boot.bin")
    _UBOOT_FILE.write_bytes(uboot_data)

    async with AsyncExitStack() as stack:
        # OCD server
        device.logger.info("Start OpenOCD server")
        ocd_server = ocd.run_server_in_background(
            logger=device.logger.getChild("ocd.server")
        )
        await stack.enter_async_context(ocd_server)

        # OCD client
        device.logger.info("Connect OpenOCD client")
        ocd_client = ocd.Client(logger=device.logger.getChild("ocd.client"))
        await stack.enter_async_context(ocd_client)

        # Low-level OCD control
        device.logger.info("Reset hardware")
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
