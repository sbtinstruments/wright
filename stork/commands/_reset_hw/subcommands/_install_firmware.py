import asyncio
from contextlib import AsyncExitStack
from functools import partial
from pathlib import Path
from typing import Callable, Optional

from .... import openocd as ocd
from ....console import Console
from ....hardware import Hardware
from ....util import split_file
from ..._command import StepByStepCommand
from ..._step import RequestConfirmation
from ._jtag_boot_to_uboot import jtag_boot_to_uboot
from ._initialize_network import initialize_network


async def install_firmware(
    console: Console,
    hardware: Hardware,
    tftp_host: str,
    tftp_port: int,
    output_cb: Optional[Callable[[str], None]] = None,
) -> StepByStepCommand:
    async with AsyncExitStack() as stack:
        # OCD server
        yield "Start OpenOCD server"
        ocd_server = ocd.Server(
            "green_mango.cfg", output_cb=partial(output_cb, source="ocd.server")
        )
        await stack.enter_async_context(ocd_server)

        # OCD client
        yield "Connect OpenOCD client"
        ocd_client = ocd.Client(output_cb=partial(output_cb, source="ocd.client"))
        # Wait until the server is ready
        await asyncio.sleep(2)
        await stack.enter_async_context(ocd_client)

        yield RequestConfirmation(
            "Ensure that:\n"
            "  1. The hardware is connected via:\n"
            "     a) JTAG\n"
            "     b) Serial\n"
            "     c) Ethernet (e.g., via a USB-to-ethernet adapter)\n"
            "  2. The 2-pin jumper is inserted\n"
            "  3. The hardware is powered up"
        )

        yield "Boot to U-boot via JTAG"
        async for step in jtag_boot_to_uboot(ocd_client, hardware):
            yield step

        await console.force_prompt()

        yield "Initialize network on the hardware"
        await initialize_network(console, tftp_host, tftp_port)

        async for step in write_fw_to_flash(console, hardware.value):
            yield step


async def write_fw_to_flash(console: Console, target: str) -> StepByStepCommand:
    await console.force_prompt()
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
