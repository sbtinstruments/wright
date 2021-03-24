import asyncio
from contextlib import AsyncExitStack
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from .... import openocd as ocd
from ....command import StepByStepCommand
from ....console import Console
from ....util import split_file

if TYPE_CHECKING:
    from .._green_mango import GreenMango


async def install_firmware(board: "GreenMango") -> StepByStepCommand:
    async with AsyncExitStack() as stack:
        yield "JTAG boot"
        await board.boot_to_jtag()

        # OCD server
        yield "Start OpenOCD server"
        ocd_server = ocd.Server(
            "green_mango.cfg", output_cb=partial(board.output_cb, source="ocd.server")
        )
        await stack.enter_async_context(ocd_server)
        # Wait until the server is ready
        await asyncio.sleep(2)

        yield "Boot to U-boot via JTAG"
        async for step in board.commands.jtag_boot_to_uboot():
            yield step

        yield "Initialize network on the hardware"
        await board.initialize_network()

        async for step in write_fw_to_flash(board.console, board.bd.hardware.value):
            yield step


async def write_fw_to_flash(console: Console, target: str) -> StepByStepCommand:
    yield "Probe FLASH memory"
    await console.cmd("sf probe")
    # First, erase the entire FLASH memory
    yield "Erase FLASH memory"
    await console.cmd(f"sf erase 0 {hex(16 * 1024**2)}")  # 16 MiB
    # Second, write `bin_path` to FLASH memory.
    #
    # `bin_path` consists mostly of null-bytes that we
    # can skip. This saves us a lot of transfer time.
    bin_path = Path(f"{target}-boot-with-u-boot-env.bin")
    # We actually don't need to physically split the files anymore.
    # This is a remant from the days of Xilinx' program_flash utility.
    # TODO: Use offsets into the file instead.
    parts = split_file(bin_path)
    for part in parts:
        yield f"Transfer ({part.path.stem}) to device"
        await console.cmd(f"tftpboot 0x6000000 {part.path}")
        yield f"Write {part.path.stem} to FLASH memory"
        size = part.path.stat().st_size
        cmd = f"sf write 0x6000000 {hex(part.offset)} {hex(size)}"
        await console.cmd(cmd)
