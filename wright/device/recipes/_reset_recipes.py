import logging
from pathlib import Path

import anyio

from .._device import Device
from ..execution_context import ExternalUboot, QuietLinux, Uboot, enter_context

_LOGGER = logging.getLogger(__name__)


async def reset_firmware(device: Device, firmware_image: Path) -> None:
    """Remove any existing firmware and write the given image to the device."""
    with anyio.fail_after(110):
        async with enter_context(ExternalUboot, device) as uboot:
            # First, erase the entire FLASH memory
            await uboot.erase_flash()
            # Second, write the firmware image to FLASH memory.
            await uboot.write_image_to_flash(firmware_image)


async def reset_software(device: Device, software_image: Path) -> None:
    """Remove any existing software and write the given images to the device."""
    with anyio.fail_after(70):
        async with enter_context(Uboot, device) as uboot:
            await uboot.partition_mmc()
            # We must power-cycle the device so that U-boot recognizes the
            # new partitioning.
            await device.hard_power_off()

        async with enter_context(Uboot, device) as uboot:
            # Write to both "system" partitions so that we have a working fall-back
            # in case of a broken (interrupted) software update. This is part of the
            # dual boot strategy.
            await uboot.write_image_to_mmc(
                software_image, uboot.mmc.system0, uboot.mmc.system1
            )


async def reset_config(device: Device, config_image: Path) -> None:
    """Remove any existing config and write the given images to the device."""
    with anyio.fail_after(40):
        async with enter_context(Uboot, device) as uboot:
            # There is a single copy of the config image
            await uboot.write_image_to_mmc(config_image, uboot.mmc.config)


async def reset_data(device: Device) -> None:
    """Remove all data on the device."""
    # TODO: Find an alternative execution context for this step.
    # Currently, we rely on the device's Linux distribution (via `QuietLinux`).
    # This is brittle. Slight changes to, e.g., the init scripts can invalidate
    # this recipe. For example, when we renamed "/etc/init.d/Amonit" to
    # "/etc/init.d/S99monit".
    # This step is also very slow because we have to wait for the Linux distribution
    # to fully boot. All we really need to do is format an ext4 partition. There
    # must be a better way.
    # Maybe we can just raw copy an existing EXT4-formatted partition to the raw MMC.
    # We can do that directly through U-boot (no Linux required).
    with anyio.fail_after(100):
        async with enter_context(QuietLinux, device) as linux:
            await linux.reset_data()
