from contextlib import AsyncExitStack
from datetime import datetime
from logging import Logger, getLogger
from pathlib import Path
from typing import Any, Optional

from anyio.abc import TaskGroup

from ...branding import Branding
from ...config import create_config_image
from ...hardware import (
    DeviceDescription,
    GpioBootModeControl,
    GreenMango,
    Hardware,
    RelayPowerControl,
    recipes,
)
from ...swupdate import SwuFiles
from ...tftp import AsyncTFTPServer
from ...util import TEMP_DIR

_LOGGER = getLogger(__name__)


async def reset_hw(
    swu: Path,
    *,
    hardware: Hardware,
    branding: Branding,
    hostname: str,
    tty: Optional[Path] = None,
    tftp_host: Optional[str] = None,
    tftp_port: Optional[int] = None,
    logger: Optional[Logger] = None,
    skip_install_firmware: Optional[bool] = None,
) -> None:
    """Reset hardware to mint condition."""
    if logger is None:
        logger = _LOGGER
    # Device description
    desc_kwargs: dict[str, Any] = {}
    if tty is not None:
        desc_kwargs["tty"] = tty
    if tftp_host is not None:
        desc_kwargs["tftp_host"] = tftp_host
    if tftp_port is not None:
        desc_kwargs["tftp_port"] = tftp_port
    desc = DeviceDescription(
        hardware=hardware,
        power_control=RelayPowerControl(1),
        boot_mode_control=GpioBootModeControl(15),
        **desc_kwargs,
    )
    logger.info('Using TTY "%s"', desc.tty)
    await reset_hw2(
        desc,
        hostname,
        logger,
        swu,
        branding=branding,
        skip_install_firmware=skip_install_firmware,
    )


async def reset_hw2(
    desc: DeviceDescription,
    hostname: str,
    logger: Logger,
    swu: Path,
    *,
    branding: Branding,
    skip_install_firmware: Optional[bool] = None,
) -> None:
    """Reset hardware to mint condition."""
    start = datetime.now()

    async with AsyncExitStack() as stack:
        # SWU
        logger.info("Extract files from SWU")
        swu_logger = None if logger is None else logger.getChild("swu")
        swu_files = await SwuFiles.from_swu(swu, TEMP_DIR, logger=swu_logger)
        bundle = swu_files.devices[desc.hardware]

        # Config image
        logger.info("Create config image")
        config_logger = None if logger is None else logger.getChild("config")
        config_image = TEMP_DIR / "config.img"
        await create_config_image(
            config_image,
            hardware=desc.hardware,
            branding=branding,
            hostname=hostname,
            logger=config_logger,
        )

        # TFTP server
        #
        # Serves everything inside `TEMP_DIR`
        logger.info("Start TFTP server")
        tftp_server = AsyncTFTPServer(
            desc.tftp_host, desc.tftp_port, directory=TEMP_DIR
        )
        await stack.enter_async_context(tftp_server)

        def _device_factory(tg: TaskGroup) -> GreenMango:
            return GreenMango(tg, hostname, desc, logger=logger)

        # Reset firmware
        if not skip_install_firmware:
            await recipes.retry(
                recipes.reset_firmware,
                bundle.firmware,
                device_factory=_device_factory,
                logger=logger,
            )

        # Reset software
        await recipes.retry(
            recipes.reset_software,
            bundle.software,
            config_image,
            device_factory=_device_factory,
            logger=logger,
        )

        # Reset data
        await recipes.retry(
            recipes.reset_data,
            device_factory=_device_factory,
            logger=logger,
        )

    end = datetime.now()
    delta = end - start
    logger.info(f"Reset hardware successful (took {delta})")
