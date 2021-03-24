from typing import TYPE_CHECKING

from ....command import StepByStepCommand

if TYPE_CHECKING:
    from .._green_mango import GreenMango


async def install_software(board: "GreenMango") -> StepByStepCommand:
    yield "Reset hardware"
    await board.reset_and_wait_for_prompt()

    yield "Partition the MMC memory"
    await board.console.cmd(
        'gpt write mmc 0 "name=system0,size=150MiB;name=system1,size=150MiB;name=config,size=100MiB;name=data,size=0"'
    )

    yield "Reset hardware"
    await board.reset_and_wait_for_prompt()

    yield "Initialize network on the hardware"
    await board.initialize_network()

    image = f"{board.bd.hardware.value}-system.img"
    yield f"Transfer {image} to the hardware"
    await board.console.cmd(f"tftpboot 0x6000000 {image}")
    yield f"Write {image} to the MMC memory"
    # Writes system image (from DDR RAM) to partition "system0".
    # Note that the sector size is 512 byes (0x200). Therefore, we
    # write 0x4B000=0x9600000/0x200 sectors (i.e., 307200=150MiB/512B).
    await board.console.cmd("mmc write 0x6000000 0x00022 0x4B000")
    # Also write system image to partition "system1".
    await board.console.cmd("mmc write 0x6000000 0x4b022 0x4B000")

    yield "Transfer config.img to the hardware"
    await board.console.cmd("tftpboot 0x6000000 config.img")
    yield "Write config.img to the MMC memory"
    await board.console.cmd("mmc write 0x6000000 0x96022 0x32000")
