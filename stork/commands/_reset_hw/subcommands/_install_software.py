from typing import Callable, Optional

from ....console import Console
from ....hardware import Hardware
from ..._command import StepByStepCommand
from ._initialize_network import initialize_network


async def install_software(
    console: Console,
    hardware: Hardware,
    tftp_host: str,
    tftp_port: int,
    skip_system_image: bool,
    skip_config_image: bool,
) -> StepByStepCommand:
    yield "Partition the MMC memory"
    await console.cmd(
        'gpt write mmc 0 "name=system0,size=150MiB;name=system1,size=150MiB;name=config,size=100MiB;name=data,size=0"'
    )
    yield "Reset hardware"
    await console.reset()
    await console.force_prompt()

    yield "Initialize network on the hardware"
    await initialize_network(console, tftp_host, tftp_port)

    if not skip_system_image:
        image = f"{hardware.value}-system.img"
        yield f"Transfer {image} to the hardware"
        await console.cmd(f"tftpboot 0x6000000 {image}")
        yield f"Write {image} to the MMC memory"
        # Writes system image (from DDR RAM) to partition "system0".
        # Note that the sector size is 512 byes (0x200). Therefore, we
        # write 0x4B000=0x9600000/0x200 sectors (i.e., 307200=150MiB/512B).
        await console.cmd("mmc write 0x6000000 0x00022 0x4B000")
        # Also write system image to partition "system1".
        await console.cmd("mmc write 0x6000000 0x4b022 0x4B000")

    if not skip_config_image:
        yield "Transfer config.img to the hardware"
        await console.cmd("tftpboot 0x6000000 config.img")
        yield "Write config.img to the MMC memory"
        await console.cmd("mmc write 0x6000000 0x96022 0x32000")
