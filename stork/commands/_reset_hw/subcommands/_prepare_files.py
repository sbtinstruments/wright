import os
import shutil
from functools import partial
from importlib import resources
from pathlib import Path
from typing import Callable, Optional

from ....branding import Branding
from ....config import create_config_image
from ....hardware import Hardware
from ....swupdate import extract_swu
from ....openocd import configs as ocd_configs

from ..._command import StepByStepCommand


async def prepare_files(
    dir: Path,
    swu: Path,
    hardware: Hardware,
    branding: Branding,
    hostname: str,
    fsbl_elf: Path,
    uboot_bin: Path,
    output_cb: Optional[Callable[[str], None]] = None,
) -> StepByStepCommand:
    yield "Remove any lingering artifacts from previous runs"
    shutil.rmtree(dir, ignore_errors=True)

    yield "Copy over input files"
    # Copy over files to the temporary dir
    dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(swu, dir)
    # Copy over the first-stage boot loader (FSBL).
    #
    # Note that this is NOT the FSBL that will end up on the hardware.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the hardware over JTAG.
    shutil.copy(fsbl_elf, dir / "fsbl.elf")
    # Copy over the second-stage boot loader (U-boot).
    #
    # Like with the FSBL, this is NOT the U-boot that ends up on the hardware.
    shutil.copy(uboot_bin, dir / "u-boot.bin")
    # Copy the OpenOCD config file
    cfg = resources.read_binary(ocd_configs, "green_mango.cfg")
    (dir / "green_mango.cfg").write_bytes(cfg)
    # Change to the given directory
    os.chdir(dir)
    
    yield "Extract files from SWU"
    swu_output = partial(output_cb, source="swu")
    await extract_swu(Path(swu.name), output_cb=swu_output)

    yield "Create config image"
    config_output = partial(output_cb, source="config")
    await create_config_image(
        hardware=hardware, branding=branding, hostname=hostname, output_cb=config_output
    )
