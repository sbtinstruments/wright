import os
import shutil
from functools import partial
from importlib import resources
from pathlib import Path
from typing import Callable, Optional
import filecmp

from ....branding import Branding
from ....config import create_config_image
from ....hardware import Hardware
from ....swupdate import extract_swu
from ....openocd import configs as ocd_configs

from ....command import StepByStepCommand


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
    yield "Make working directory"
    dir.mkdir(parents=True, exist_ok=True)

    # SWU file
    yield "Copy over SWU file"
    swu_changed = copy_file_if_different(swu, dir / swu.name, shallow_compare=True)

    # Copy over the first-stage boot loader (FSBL).
    #
    # Note that this is NOT the FSBL that will end up on the hardware.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the hardware over JTAG.
    yield "Copy over FSBL"
    copy_file_if_different(fsbl_elf, dir / "fsbl.elf")

    # Copy over the second-stage boot loader (U-boot).
    #
    # Like with the FSBL, this is NOT the U-boot that ends up on the hardware.
    yield "Copy over U-boot"
    copy_file_if_different(uboot_bin, dir / "u-boot.bin")

    # Copy the OpenOCD config file
    yield "Copy OpenOCD config file"
    cfg = resources.read_binary(ocd_configs, "green_mango.cfg")
    (dir / "green_mango.cfg").write_bytes(cfg)

    # Change to the given directory
    yield "Change to the working directory"
    os.chdir(dir)

    # Extract SWU contents
    if swu_changed:
        yield "Extract files from SWU"
        swu_output = partial(output_cb, source="swu")
        await extract_swu(Path(swu.name), output_cb=swu_output)

    # Config image
    yield "Create config image"
    config_output = partial(output_cb, source="config")
    await create_config_image(
        hardware=hardware, branding=branding, hostname=hostname, output_cb=config_output
    )


def copy_file_if_different(
    src: Path, dst: Path, *, shallow_compare: bool = False
) -> bool:
    """Copy file from `src` to `dst` if they differ.

    Returns `True` if we did a copy.
    """
    if not dst.exists() or not filecmp.cmp(src, dst, shallow=shallow_compare):
        shutil.copyfile(src, dst)
        return True
    return False
