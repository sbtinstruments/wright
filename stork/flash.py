import os
import subprocess
from pathlib import Path

from .util import split_file

FSBL_ELF = os.environ.get("STORK_FSBL_ELF", "fsbl.elf")

PROGRAM_FLASH_UTIL = os.environ.get(
    "STORK_PROGRAM_FLASH_UTIL", "/opt/Xilinx/SDK/2018.3/bin/program_flash"
)


def program_flash(target: str) -> None:
    """Overwrite FLASH memory with the contents of the boot BIN file."""
    bin_path = Path(f"{target}-boot-with-u-boot-env.bin")
    # First, erase the entire FLASH memory.
    #
    # Note that `bin_path` is NOT transferred! It is only used for its
    # file size (16 MiB) so that the entire FLASH  will be erased.
    # This is a good since, since the file transfer itself is really slow.
    program_flash_util(bin_path, "-erase_only")
    # Second, write `bin_path` to FLASH memory.
    #
    # It is very slow to transfer data from the host computer to the
    # target board. Therefore, we want to transfer as little data as
    # possible.
    #
    # Fortunately, `bin_path` consists mostly of null-bytes that we
    # can skip. This saves us a lot of time.
    parts = split_file(bin_path)
    for part in parts:
        # Transfer and write each individual part to FLASH memory.
        program_flash_util(part.path, "-no_erase", "-offset", str(part.offset))


def program_flash_util(bin_path: Path, *args: str) -> None:
    """Call the "program_flash" util from Xilinx."""
    args = [
        "-f",
        str(bin_path),
        *args,
        "-flash_type",
        "qspi-x4-single",
        "-fsbl",
        FSBL_ELF,
        "-cable",
        "type",
        "xilinx_tcf",
        "url",
        "TCP:127.0.0.1:3121",
    ]
    subprocess.run([PROGRAM_FLASH_UTIL, *args], check=True)