from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from anyio.abc import TaskGroup
from anyio.lowlevel import checkpoint

from ....util import split_file
from ._base import _ConsoleBase

if TYPE_CHECKING:
    from .._green_mango import GreenMango


@dataclass(frozen=True)
class MmcPartition:
    """Partition in MMC-based storage."""

    offset: int  # [sectors]
    length: int  # [sectors]


@dataclass(frozen=True)
class Mmc:
    """MultiMediaCard storage."""

    sector_size: int = 0x200  # 512 bytes
    # 0x4B000=0x9600000/0x200 sectors (i.e., 307200=150MiB/512B).
    system0: MmcPartition = MmcPartition(0x00022, 0x4B000)
    system1: MmcPartition = MmcPartition(0x4B022, 0x4B000)
    config: MmcPartition = MmcPartition(0x96022, 0x32000)


class Uboot(_ConsoleBase):
    """On-device U-boot installation."""

    def __init__(self, device: "GreenMango", tg: TaskGroup) -> None:
        prompt = f"\r\n{device.desc.hardware.value}> "
        super().__init__(device, tg, prompt)
        self.mmc = Mmc()
        # This is the memory address that we use as temporary scratch space for
        # e.g., file transfers.
        self._default_memory_address = 0x6000000
        self._initialized_network = False
        self._initialized_usb = False
        self._probed_flash = False

    async def write_image_to_mmc(self, file: Path, *partitions: MmcPartition) -> None:
        """Write file system image from host to device's MMC."""
        await self.copy_to_memory(file)
        for partition in partitions:
            await self.write_memory_to_mmc(partition)

    async def partition_mmc(self) -> None:
        """Partition the device's MMC memory."""
        self.logger.info("Partition MMC memory")
        await self.cmd(
            'gpt write mmc 0 "'
            "name=system0,size=150MiB;"
            "name=system1,size=150MiB;"
            "name=config,size=100MiB;"
            'name=data,size=0"'
        )
        # U-boot won't recognize the new partitioning right away.
        # No combination of `mmc dev 0`, `mmc rescan`, etc. will do.
        # We need to restart the entire device. Therefore, we close
        # this context.
        await self.aclose()

    async def write_memory_to_mmc(
        self, partition: MmcPartition, *, memory_address: Optional[int] = None
    ) -> None:
        """Write from device memory to the given MMC partition.

        Use this to write an in-memory file system image to the MMC.
        """
        if memory_address is None:
            memory_address = self._default_memory_address
        memory_address_hex = hex(memory_address)
        self.logger.info(
            f'Write memory at {memory_address_hex} to MMC partition "{partition}"'
        )
        await self.cmd(
            f"mmc write {memory_address_hex} "
            f"{hex(partition.offset)} "
            f"{hex(partition.length)}"
        )

    async def write_image_to_flash(self, file: Path) -> None:
        """Write the given image file to the FLASH memory on this device.

        Remember to erase the FLASH memory first.
        """
        # An image usually consists mostly of null-bytes. We can skip
        # said null bytes. This saves us a lot of transfer time.
        #
        # We actually don't need to physically split the files anymore.
        # This is a remnant from the days of the Xilinx' program_flash utility.
        # TODO: Use offsets into the firmware image instead.
        parts = split_file(file)
        for part in parts:
            await self.copy_to_memory(part.path)
            length = part.path.stat().st_size
            await self.write_memory_to_flash(part.offset, length)

    async def erase_flash(self) -> None:
        """Erase the flash memory on this device."""
        await self._probe_flash()
        self.logger.info("Erase FLASH memory")
        size = 16 * 1024 ** 2  # 16 MiB
        await self.cmd(f"sf erase 0 {hex(size)}")

    async def _probe_flash(self) -> None:
        """Initialize the flash subsystem.

        Only probes on the first call. Does nothing on subsequent calls.
        """
        # Early out
        if self._probed_flash:
            await checkpoint()
            self.logger.debug("Already probed FLASH")
            return
        self.logger.info("Probe FLASH memory")
        await self.cmd("sf probe")
        self._probed_flash = True

    async def write_memory_to_flash(
        self, offset: int, length: int, *, memory_address: Optional[int] = None
    ) -> None:
        """Write from device memory to the FLASH memory at the given offset."""
        if memory_address is None:
            memory_address = self._default_memory_address
        memory_address_hex = hex(memory_address)
        offset_hex = hex(offset)
        length_hex = hex(length)
        await self._probe_flash()
        self.logger.info(
            "Write memory at %s to FLASH (offset:%s length:%s)",
            memory_address_hex,
            offset_hex,
            length_hex,
        )
        await self.cmd(f"sf write {memory_address_hex} {offset_hex} {length_hex}")

    async def copy_to_memory(
        self, file: Path, *, address: Optional[int] = None
    ) -> None:
        """Copy the given file to the device at the given memory address."""
        if address is None:
            address = self._default_memory_address
        address_hex = hex(address)
        await self._initialize_network()
        self.logger.info("Copy %s to device memory at %s", str(file), address_hex)
        await self.cmd(f"tftpboot {address_hex} {file}")

    async def boot_to_quiet_linux(self) -> None:
        """Start the linux boot process with the lowest log level."""
        # Disable kernel logging as it messes with the serial output.
        # That is, sometimes the kernel will spam the serial line with
        # driver info messages. Said messages interfere with how we parse
        # the serial line.
        await self.cmd("setenv bootargs loglevel=0")
        await self.boot_to_linux()

    async def boot_to_linux(self) -> None:
        """Start the linux boot process."""
        await self.cmd("boot", wait_for_prompt=False)
        # At this point, this U-boot context is no longer valid. Therefore,
        # we close this context.
        await self.aclose()

    async def _initialize_network(self, *, force: bool = False) -> None:
        """Initialize the device for network communication.

        Only initializes on the first call. Does nothing on subsequent calls.
        """
        # Early out
        if self._initialized_network and not force:
            await checkpoint()
            self.logger.debug("Already initialized network")
            return
        self.logger.info("Initialize network")
        await self._initialize_usb(force=force)
        # We just want an IP address. Not start a TFTP server.
        # Unfortunately, the `dhcp` command does both. When the latter
        # fails, it returns with error code 1. Therefore, we ignore the
        # error code.
        await self.cmd("dhcp", check_error_code=False)
        await self.cmd(f"setenv serverip {self._dev.desc.tftp_host}")
        await self.cmd(f"setenv tftpdstp {self._dev.desc.tftp_port}")
        # Increase block and window sizes to improve transfer speeds.
        # In practice, this improves transfer speeds tenfold. E.g.,
        # from ~1 MB/s to ~10 MB/s.
        await self.cmd("setenv tftpblocksize 1468")
        await self.cmd("setenv tftpwindowsize 256")
        # We exploit the "tftpboot" command and make it do arbitrary file transfers.
        # In order to do so, we disable the "boot" aspect of it with `autostart=no`.
        await self.cmd("setenv autostart no")
        self._initialized_network = True

    async def _initialize_usb(self, *, force: bool = False) -> None:
        """Initialize the device for USB communication.

        Only initializes on the first call. Does nothing on subsequent calls.
        """
        # Early out
        if self._initialized_usb and not force:
            await checkpoint()
            self.logger.debug("Already initialized USB subsystem")
            return

        if force:
            self.logger.info("Reset USB subsystem")
            await self.cmd("usb reset")

        # U-boot doesn't handle "quirky" USB devices as well as Linux (U-boot
        # doesn't have a "quirks table" like Linux). Consequently, U-boot may
        # spuriously issue a "Loading: EHCI timed out on TD" error if a USB
        # device is a bit slower than it's non-quirky peers. E.g.:
        #  * A USB HDD takes some time to spin up
        #  * A USB-ethernet adapter takes some time to initialize
        #
        # For now, we propagate the error to the caller. We recommend to put
        # a timeout on the USB calls in order to fail fast.
        #
        # See the following for details:
        #
        # Rejected patch from 2020:
        # https://patchwork.ozlabs.org/project/uboot/patch/20200226112955.7930-1-lukma@denx.de/
        #
        # Out-of-tree patch from 2017:
        # https://forum.doozan.com/read.php?3,35295
        #
        # The line of code that prints the "EHCI timed out..." warning:
        # https://github.com/u-boot/u-boot/blob/a1e95e3805eacca1162f6049dceb9b1d2726cbf5/drivers/usb/host/ehci-hcd.c#L649
        await self.cmd("usb start")
        self._initialized_usb = True

    async def _boot(self) -> None:
        await self._dev.hard_restart()

    async def __aenter__(self) -> Uboot:
        await self._boot()
        # Enter console
        await super().__aenter__()
        return self
