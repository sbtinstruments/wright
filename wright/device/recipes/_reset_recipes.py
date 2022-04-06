import logging
from pathlib import Path

import anyio

from .._device import Device
from ..execution_context import (
    DeviceUboot,
    WrightLiveLinux,
    WrightLiveUboot,
    enter_context,
)

_LOGGER = logging.getLogger(__name__)


async def reset_firmware(device: Device, firmware_image: Path) -> None:
    """Remove any existing firmware and write the given image to the device."""
    with anyio.fail_after(110):
        async with enter_context(WrightLiveUboot, device) as uboot:
            # First, erase the entire FLASH memory
            await uboot.erase_flash()
            # Second, write the firmware image to FLASH memory.
            await uboot.write_image_to_flash(firmware_image)


async def reset_operating_system(device: Device, operating_system_image: Path) -> None:
    """Remove any existing operating system and write the given images to the device."""
    with anyio.fail_after(100):
        async with enter_context(DeviceUboot, device) as uboot:
            await uboot.partition_mmc()
            # We must power-cycle the device so that U-boot recognizes the
            # new partitioning.
            await device.hard_power_off()

        async with enter_context(DeviceUboot, device) as uboot:
            # Write to both "system" partitions so that we have a working fall-back
            # in case of a broken (interrupted) software update. This is part of the
            # dual boot strategy.
            await uboot.write_image_to_mmc(
                operating_system_image, uboot.mmc.system0, uboot.mmc.system1
            )


async def reset_config(device: Device, config_image: Path) -> None:
    """Remove any existing config and write the given images to the device."""
    with anyio.fail_after(60):
        async with enter_context(DeviceUboot, device) as uboot:
            # There is a single copy of the config image
            await uboot.write_image_to_mmc(config_image, uboot.mmc.config)


async def reset_data(device: Device) -> None:
    """Remove all data on the device."""
    with anyio.fail_after(60):
        async with enter_context(WrightLiveLinux, device) as linux:
            await linux.reset_data()
