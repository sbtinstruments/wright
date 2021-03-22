from stork.console import Console, Mode

from ..._command import StepByStepCommand


async def erase_data(
    console: Console,
) -> StepByStepCommand:
    yield "Format data partition of MMC memory"
    # The umount command will fail if the data partition is invalid
    # or non-existing. Therefore, we skip the error code check.
    await console.cmd("umount /media/data", check_error_code=False)
    await console.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")
