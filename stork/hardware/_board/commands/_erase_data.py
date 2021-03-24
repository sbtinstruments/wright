from typing import TYPE_CHECKING

from ....command import StepByStepCommand

if TYPE_CHECKING:
    from .._green_mango import GreenMango


async def erase_data(board: "GreenMango") -> StepByStepCommand:
    # Boot to operating system
    async for step in board.commands.boot_to_os():
        yield step

    yield "Format data partition of MMC memory"
    # The umount command will fail if the data partition is invalid
    # or non-existing. Therefore, we skip the error code check.
    await board.console.cmd("umount /media/data", check_error_code=False)
    await board.console.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")
