import asyncio
from asyncio.subprocess import PIPE, STDOUT
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .util import split_file
from .console import Console

FSBL_ELF = os.environ.get("STORK_FSBL_ELF", "fsbl.elf")

_OPENOCD_EXE = Path(os.environ.get(
    "STORK_OPENOCD_EXE",
    # TODO: Uae another default for this
    "/home/fpa/Downloads/xpack-openocd-0.11.0-1-linux-x64/xpack-openocd-0.11.0-1/bin/openocd"
))


async def program_flash(
    console: Console,
    target: str, stdout: Optional[Callable[[str], None]] = None
) -> None:
    """Overwrite FLASH memory with the contents of the boot BIN file."""
    #bin_path = Path(f"{target}-boot-with-u-boot-env.bin")
    task = asyncio.create_task(openocd(stdout))
    await asyncio.sleep(1)
    
    await task
    


async def openocd(stdout: Optional[Callable[[str], None]] = None) -> None:
    """Call the "program_flash" util from Xilinx."""
    args = [
        "-f",
        _OPENOCD_EXE.parent / "../bactobox.cfg"
    ]
    process = await asyncio.create_subprocess_exec(
        _OPENOCD_EXE, *args, stdout=PIPE, stderr=STDOUT
    )
    while True:
        stdout_line = await process.stdout.readline()
        if stdout_line == b"":
            break
        if stdout is not None:
            stdout(stdout_line.decode())
    rc = await process.wait()
    if rc != 0:
        raise RuntimeError(f"Process returned non-zero code: {rc}")
