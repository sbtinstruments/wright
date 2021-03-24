from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from .... import openocd as ocd
from ....command import StepByStepCommand

if TYPE_CHECKING:
    from .._green_mango import GreenMango


async def jtag_boot_to_uboot(board: "GreenMango") -> StepByStepCommand:
    fsbl = Path("fsbl.elf")
    uboot = Path("u-boot.bin")

    # OCD client
    yield "Connect OpenOCD client"
    ocd_client = ocd.Client(output_cb=partial(board.output_cb, source="ocd.client"))

    async with ocd_client:
        yield "Reset hardware"
        await ocd_client.cmd("reset halt")
        yield "Copy FSBL to device memory"
        await ocd_client.cmd(f"load_image {fsbl} 0 elf")
        yield "Execute FSBL"
        await ocd_client.cmd("resume 0")
        await ocd_client.cmd("sleep 4000")
        yield "Copy U-boot to device memory"
        await ocd_client.cmd("halt")
        await ocd_client.cmd(f"load_image {uboot} 0x04000000 bin")
        yield "Execute U-boot"
        await ocd_client.cmd("resume 0x04000000")
        yield "Enter U-boot prompt"
        await board.console.force_prompt()
