from datetime import datetime
from logging import Logger, getLogger
from pathlib import Path
from typing import Optional

from ..config import create_config_image
from ..config.branding import Branding
from ..device import DeviceDescription
from ..device.green_mango import recipes
from ..swupdate import SwuFiles
from ..util import TEMP_DIR

_LOGGER = getLogger(__name__)


async def reset_device(
    desc: DeviceDescription,
    swu: Path,
    branding: Branding,
    *,
    skip_reset_firmware: Optional[bool] = None,
    logger: Optional[Logger] = None,
) -> None:
    """Reset device to mint condition."""
    # Defaults
    if logger is None:
        logger = _LOGGER

    start = datetime.now()

    # Extract files from SWU
    logger.info("Extract files from SWU")
    swu_files = await SwuFiles.from_swu(swu, TEMP_DIR, logger=logger.getChild("swu"))
    bundle = swu_files.devices[desc.device_type]

    # Create config image
    logger.info("Create config image")
    config_image = TEMP_DIR / "config.img"
    await create_config_image(
        config_image,
        device_type=desc.device_type,
        branding=branding,
        hostname=desc.link.communication.hostname,
        logger=logger.getChild("config"),
    )

    # Reset firmware
    if not skip_reset_firmware:
        await recipes.retry(
            recipes.reset_firmware,
            bundle.firmware,
            device_description=desc,
            logger=logger,
        )

    # Reset software
    await recipes.retry(
        recipes.reset_software,
        bundle.software,
        config_image,
        device_description=desc,
        logger=logger,
    )

    # Reset data
    await recipes.retry(
        recipes.reset_data,
        device_description=desc,
        logger=logger,
    )

    end = datetime.now()
    delta = end - start
    logger.info("Reset device successful (took %s)", delta)
