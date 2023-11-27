from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import datetime, timedelta
from logging import Logger, getLogger
from pathlib import Path
from typing import Optional, Union

from ..config import create_config_image
from ..device.models import Branding, HardwareIdentificationGroup
from ..device import Device, DeviceCondition, DeviceDescription, DeviceType, recipes
from ..progress import Idle, ProgressManager, StatusMap, StatusStream
from ..swupdate import MultiBundle
from ..util import TEMP_DIR
from ._power_off_on_error import power_off_on_error
from ._settings import ResetDeviceSettings
from ._step import run_step

_LOGGER = getLogger(__name__)


RESET_DEVICE_STATUS_MAP: StatusMap = {
    # TODO: Use a single source of truth: Only define the timeout parameter once.
    # Either here or in the recipes.
    "prepare": Idle(expected_duration=timedelta(seconds=60), tries=0),
    "reset_firmware": Idle(expected_duration=timedelta(seconds=110), tries=0),
    "reset_operating_system": Idle(expected_duration=timedelta(seconds=100), tries=0),
    "reset_config": Idle(expected_duration=timedelta(seconds=60), tries=0),
    "reset_data": Idle(expected_duration=timedelta(seconds=60), tries=0),
}


async def reset_device(
    device_or_desc: Union[Device, DeviceDescription],
    bundle_or_swu: Union[MultiBundle, Path],
    branding: Branding,
    *,
    settings: Optional[ResetDeviceSettings] = None,
    progress_manager: Optional[ProgressManager] = None,
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
    async with AsyncExitStack() as stack:
        if progress_manager is None:
            progress_manager = ProgressManager(
                RESET_DEVICE_STATUS_MAP, status_stream=progress_stream
            )
            await stack.enter_async_context(progress_manager)

        # Device and it's description
        if isinstance(device_or_desc, DeviceDescription):
            device = Device.from_description(device_or_desc, logger=logger)
            await stack.enter_async_context(device)
        else:
            device = device_or_desc

        # Prepare
        multi_bundle, config_image = await run_step(
            _prepare,
            device.device_type,
            device.version,
            device.link.communication.hostname,
            device.hw_ids,
            bundle_or_swu,
            branding,
            logger,  # This logger goes into `_prepare`
            progress_manager=progress_manager,
            logger=logger,  # This logger goes into `run_step`
        )
        device_bundle = multi_bundle.device_bundles[device.device_type.value]

        # Reset firmware
        await run_step(
            power_off_on_error(recipes.reset_firmware, device),
            device_bundle.firmware.file,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_firmware,
        )

        # Reset operating system
        await run_step(
            power_off_on_error(recipes.reset_operating_system, device),
            device_bundle.operating_system.file,
            multi_bundle.version,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_operating_system,
        )

        # Reset config
        await run_step(
            power_off_on_error(recipes.reset_config, device),
            config_image,
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_config,
        )

        # Reset data
        await run_step(
            power_off_on_error(recipes.reset_data, device),
            progress_manager=progress_manager,
            logger=logger,
            settings=settings.reset_data,
        )

        # Update metadata to reflect the changes
        device.metadata = device.metadata.update(
            bundle=multi_bundle,
            branding=branding,
            condition=DeviceCondition.MINT,
        )

    # TODO: Move this into the progress manager or similar
    end = datetime.now()
    delta = end - start
    logger.info("Reset device successful (took %s)", delta)


async def _prepare(
    device_type: DeviceType,
    device_version: str,
    hostname: str,
    hw_ids: HardwareIdentificationGroup,
    bundle_or_swu: Union[MultiBundle, Path],
    branding: Branding,
    logger: Logger,
) -> tuple[MultiBundle, Path]:
    if isinstance(bundle_or_swu, Path):
        # Extract files from SWU
        logger.info("Extract files from SWU")
        multi_bundle = await MultiBundle.from_swu(
            bundle_or_swu, logger=logger.getChild("swu")
        )
    else:
        multi_bundle = bundle_or_swu
    # Create config image
    logger.info("Create config image")
    config_image = TEMP_DIR / "config.img"
    await create_config_image(
        config_image,
        device_type=device_type,
        device_version=device_version,
        branding=branding,
        hostname=hostname,
        hw_ids=hw_ids,
        logger=logger.getChild("config"),
    )
    return multi_bundle, config_image
