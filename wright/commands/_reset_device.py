from __future__ import annotations

from datetime import datetime, timedelta
from logging import Logger, getLogger
from pathlib import Path
from typing import Optional

from ..config import create_config_image
from ..config.branding import Branding
from ..device import DeviceDescription
from ..device.green_mango import recipes
from ..progress import Idle, ProgressManager, StatusMap, StatusStream
from ..swupdate import SwuFiles, UpdateBundle
from ..util import TEMP_DIR
from ._settings import ResetDeviceSettings
from ._step import run_step
from ._with_device import with_device

_LOGGER = getLogger(__name__)


RESET_DEVICE_STATUS_MAP: StatusMap = {
    # TODO: Use a single source of truth: Only define the timeout parameter once.
    # Either here or in the recipes.
    "prepare": Idle(timedelta(seconds=60), 0),
    "reset_firmware": Idle(timedelta(seconds=110), 0),
    "reset_software": Idle(timedelta(seconds=70), 0),
    "reset_config": Idle(timedelta(seconds=40), 0),
    "reset_data": Idle(timedelta(seconds=90), 0),
}


async def reset_device(
    desc: DeviceDescription,
    swu: Path,
    branding: Branding,
    *,
    settings: Optional[ResetDeviceSettings] = None,
    progress_stream: Optional[StatusStream] = None,
    logger: Optional[Logger] = None,
) -> None:
    """Reset device to mint condition."""
    # Defaults
    if settings is None:
        settings = ResetDeviceSettings()
    if logger is None:
        logger = _LOGGER

    start = datetime.now()

    progress_manager = ProgressManager(
        RESET_DEVICE_STATUS_MAP, status_stream=progress_stream
    )
    async with progress_manager:
        # Prepare
        bundle, config_image = await run_step(
            _prepare,
            desc,
            swu,
            branding,
            logger,  # This logger goes into `_prepare`
            progress_manager=progress_manager,
            logger=logger,  # This logger goes into `run_step`
        )

        # Reset firmware
        await run_step(
            with_device(recipes.reset_firmware, device_description=desc, logger=logger),
            bundle.firmware,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_firmware,
        )

        # Reset software
        await run_step(
            with_device(recipes.reset_software, device_description=desc, logger=logger),
            bundle.software,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_software,
        )

        # Reset config
        await run_step(
            with_device(recipes.reset_config, device_description=desc, logger=logger),
            config_image,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_config,
        )

        # Reset data
        await run_step(
            with_device(recipes.reset_data, device_description=desc, logger=logger),
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_data,
        )

    # TODO: Move this into the progress manager or similar
    end = datetime.now()
    delta = end - start
    logger.info("Reset device successful (took %s)", delta)


async def _prepare(
    desc: DeviceDescription,
    swu: Path,
    branding: Branding,
    logger: Logger,
) -> tuple[UpdateBundle, Path]:
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
    return bundle, config_image
