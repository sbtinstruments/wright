import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from ...branding import Branding
from ...config import create_config_image
from ...hardware import Hardware
from ...util import extract_swu, get_local_ip
from .._command import StepByStepCommand
from ._steps import reset_hw_steps
from ._validation import raise_if_bad_hostname

_LOGGER = logging.getLogger(__name__)

TEMP_DIR = Path(f"/tmp/stork-{os.getpid()}")


async def reset_hw(
    swu: Path,
    *,
    hardware: Hardware,
    branding: Branding,
    hostname: str,
    fsbl_elf: Path,
    tty: Optional[Path] = None,
    tftp_host: Optional[str] = None,
    tftp_port: Optional[int] = None,
    output_cb: Optional[Callable[[str], None]] = None,
    skip_program_flash: Optional[bool] = None,
    skip_system_image: Optional[bool] = None,
    skip_config_image: Optional[bool] = None,
    restore_default_uboot_env: Optional[bool] = None,
) -> StepByStepCommand:
    # Extra validation
    raise_if_bad_hostname(hostname, hardware)
    # Default arguments
    if tty is None:
        tty = Path("/dev/ttyUSB0")
    if tftp_host is None:
        tftp_host = get_local_ip()
    if tftp_port is None:
        tftp_port = 6969
    # Set everything up so that the command can run
    yield "Extract files from SWU and prepare images"
    await prepare_files(swu, hardware, branding, hostname, fsbl_elf)
    # Run command
    try:
        steps = reset_hw_steps(
            hardware=hardware,
            hostname=hostname,
            tty=Path(tty),
            tftp_host=tftp_host,
            tftp_port=tftp_port,
            output_cb=output_cb,
            skip_program_flash=skip_program_flash,
            skip_system_image=skip_system_image,
            skip_config_image=skip_config_image,
            restore_default_uboot_env=restore_default_uboot_env,
        )
        # Perfect forwarding (similar to `yield from`)
        y = None
        while True:
            y = yield await steps.asend(y)
    except StopAsyncIteration:
        pass
    finally:
        await steps.aclose()
        shutil.rmtree(TEMP_DIR)


async def prepare_files(*args: Any) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _prepare_files, *args)


def _prepare_files(
    swu: Path,
    hardware: Hardware,
    branding: Branding,
    hostname: str,
    fsbl_elf: Path,
) -> None:
    # Remove the temporary dir to avoid lingering artifacts from
    # previous runs.
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    # Copy over files to the temporary dir and switch to said dir
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(swu, TEMP_DIR)
    # Copy over the first-stage boot loader (FSBL).
    #
    # Note that this is NOT the FSBL that will end up on the hardware.
    # It is merely a temporary boot loader used to copy the actual FSBL
    # to the hardware over JTAG.
    shutil.copy(fsbl_elf, TEMP_DIR / "fsbl.elf")
    os.chdir(TEMP_DIR)
    # Extract SWU contents. We will need it for later.
    extract_swu(Path(swu.name))
    # Create config image
    create_config_image(hardware=hardware, branding=branding, hostname=hostname)
