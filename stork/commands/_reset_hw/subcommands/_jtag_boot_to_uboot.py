from pathlib import Path

from .... import openocd as ocd
from ....hardware import Hardware
from ..._command import StepByStepCommand


async def jtag_boot_to_uboot(
    ocd_client: ocd.Client, hardware: Hardware
) -> StepByStepCommand:
    fsbl = Path("fsbl.elf")
    uboot = Path("u-boot.bin")
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
