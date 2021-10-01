from __future__ import annotations

from abc import ABC
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from anyio.abc import TaskGroup
from anyio.lowlevel import checkpoint

from ....tftp import AsyncTFTPServer
from ....util import TEMP_DIR, get_local_ip, split_file
from ... import assets
from ..._device_condition import DeviceCondition
from .._console_base import ConsoleBase
from .._deteriorate import deteriorate
from ._mmc import MmcPartition

if TYPE_CHECKING:
    from ..._device import Device


MemoryAddress = Union[str, int]


class Uboot(ConsoleBase, ABC):
    """Base class for U-boot-based execution contexts."""

    def __init__(
        self,
        device: "Device",
        tg: TaskGroup,
        prompt: str,
        *,
        force_prompt_timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        # Default arguments
        if force_prompt_timeout is None:
            force_prompt_timeout = 5
        super().__init__(
            device, tg, prompt, **kwargs, force_prompt_timeout=force_prompt_timeout
        )
        # This is the memory address that we use as temporary scratch space for
        # e.g., file transfers.
        self._default_memory_address = 0x6000000
        self._initialized_network = False
        self._initialized_usb = False
        self._probed_flash = False
        # TFTP (for file transfers)
        self._tftp_host = get_local_ip()
        self._tftp_port = 6969

    @deteriorate(DeviceCondition.USED)
    async def write_image_to_mmc(self, file: Path, *partitions: MmcPartition) -> None:
        """Write file system image from host to device's MMC."""
        await self.copy_to_memory(file)
        for partition in partitions:
            await self.write_memory_to_mmc(partition)

    @deteriorate(DeviceCondition.USED)
    async def write_memory_to_mmc(
        self, partition: MmcPartition, *, memory_address: Optional[MemoryAddress] = None
    ) -> None:
        """Write from device memory to the given MMC partition.

        Use this to write an in-memory file system image to the MMC.
        """
        memory_address_hex = await self._resolve_memory_address_to_hex(memory_address)
        self.logger.info(f'Write memory at {memory_address_hex} to "{partition}"')
        await self.cmd(
            f"mmc write {memory_address_hex} "
            f"{hex(partition.offset)} "
            f"{hex(partition.length)}"
        )

    @deteriorate(DeviceCondition.USED)
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

    @deteriorate(DeviceCondition.USED)
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

    @deteriorate(DeviceCondition.USED)
    async def write_memory_to_flash(
        self,
        offset: int,
        length: int,
        *,
        memory_address: Optional[MemoryAddress] = None,
    ) -> None:
        """Write from device memory to the FLASH memory at the given offset."""
        memory_address_hex = await self._resolve_memory_address_to_hex(memory_address)
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

    async def copy_kernel_image_to_memory(self, image: str) -> None:
        """Copy the given kernel image to device memory."""
        # U-boot has a pre-configured memory address for the kernel: kernel_addr_r.
        await self.copy_image_to_memory(image, address="kernel_addr_r")

    async def copy_rootfs_image_to_memory(self, image: str) -> None:
        """Copy the given rootfs image to device memory."""
        # U-boot has a pre-configured memory address for the rootfs: ramdisk_addr_r.
        await self.copy_image_to_memory(image, address="ramdisk_addr_r")

    async def copy_image_to_memory(
        self, image: str, *, address: Optional[MemoryAddress] = None
    ) -> None:
        """Copy the given image to device memory.

        If image is a string, we assume that it points to an internal asset.
        TODO: Add support for `Path` arguments as well.
        """
        await self.copy_asset_to_memory(image, address=address)

    async def copy_asset_to_memory(
        self, name: str, *, address: Optional[MemoryAddress] = None
    ) -> None:
        """Copy the given asset to device memory."""
        # Extract the image from the internal assets
        image_data = resources.read_binary(assets, name)
        image_file = TEMP_DIR / name
        image_file.write_bytes(image_data)
        await self.copy_to_memory(image_file, address=address)

    @deteriorate(DeviceCondition.AS_NEW)
    async def copy_to_memory(
        self, file: Path, *, address: Optional[MemoryAddress] = None
    ) -> None:
        """Copy the given file to the device at the given memory address."""
        # Early out if file is not within reach
        if not file.is_relative_to(TEMP_DIR):
            raise ValueError(
                f"Can't copy {file}. Can only copy files from within {TEMP_DIR}."
            )
        address_hex = await self._resolve_memory_address_to_hex(address)
        await self._initialize_network()
        self.logger.info("Copy %s to device memory at %s", str(file), address_hex)
        await self.cmd(f"tftpboot {address_hex} {file}")

    async def _resolve_memory_address_to_hex(
        self, address: Optional[MemoryAddress] = None
    ) -> str:
        """Return the hexidecimal value of the given address."""
        return hex(await self._resolve_memory_address(address))

    async def _resolve_memory_address(
        self, address: Optional[MemoryAddress] = None
    ) -> int:
        """Return the value of the given address.

        If `address` is a string, we assume that it corresponds to a U-boot environment
        variable. We resolve said variable.
        """
        # Return a default address if we didn't get one to begin with
        if address is None:
            await checkpoint()
            return self._default_memory_address
        # Early out if address is already resolved
        if isinstance(address, int):
            await checkpoint()
            return address
        address_hex = await self.get_env(address)
        # Convert hexidecimal string to int
        return int(address_hex, 16)

    @deteriorate(DeviceCondition.AS_NEW)
    async def set_boot_args(self, **boot_args: str) -> None:
        """Use the given keyword arguments as boot arguments."""
        raw_arg_string = " ".join(f"{key}={value}" for key, value in boot_args.items())
        await self.cmd(f"setenv bootargs {raw_arg_string}")

    @deteriorate(DeviceCondition.AS_NEW)
    async def boot_to_device_os(self) -> None:
        """Boot into the operating system installed on the device."""
        # Note that we don't use the "boot" command since it also does some PMIC
        # checks that can cause the device to shut down early. E.g., if the device
        # thinks that it woke because we inserted the power cable.
        # Instead, we run the "dualcopy_mmcboot" command directly, which takes us
        # straight into the operating system (kernel and rootfs) stored on the device.
        await self.cmd("run dualcopy_mmcboot", wait_for_prompt=False)
        # At this point, this U-boot context is no longer valid. Therefore,
        # we close this context.
        await self.aclose()

    @deteriorate(DeviceCondition.AS_NEW)
    async def boot_to_wright_live_linux(self) -> None:
        """Copy the "wright" OS to memory and boot into it."""
        await self.copy_kernel_image_to_memory("uImage-bactobox.bin")
        await self.copy_rootfs_image_to_memory(
            "bactobox-wright-image.rootfs.cpio.gz.u-boot"
        )
        # Avoid "kernel log spam" on the serial line
        await self.set_boot_args(loglevel="0")
        # Don't wait for the prompt since we transfer control to the operating
        # system from here on and out.
        await self.cmd(
            "bootm ${kernel_addr_r} ${ramdisk_addr_r} ${fdtcontroladdr}",
            wait_for_prompt=False,
        )
        # At this point, this U-boot context is no longer valid. Therefore,
        # we close this context.
        await self.aclose()

    async def get_env(self, name: str) -> str:
        """Get a U-boot environment variable by name."""
        result = await self.cmd(f"printenv {name}")
        assert isinstance(result, str), "We expect a string result from printenv"
        # If `name="my_var"` then `result="my_var=32"`. Therefore, we need
        # to strip the "my_var=" part away from the result before we return it.
        prefix = f"{name}="
        assert result.startswith(prefix)
        return result[len(prefix) :]

    async def _initialize_network(self, *, force: bool = False) -> None:
        """Initialize the device for network communication.

        Only initializes on the first call. Does nothing on subsequent calls.
        """
        # Early out
        if self._initialized_network and not force:
            await checkpoint()
            self.logger.debug("Already initialized network")
            return
        # Initialize network on host
        await self._start_tftp_server()
        # Initialize network on device
        self.logger.info("Initialize network on device")
        await self._initialize_usb(force=force)
        # We just want an IP address. Not start a TFTP server.
        # Unfortunately, the `dhcp` command does both. When the latter
        # fails, it returns with error code 1. Therefore, we ignore the
        # error code.
        await self.cmd("dhcp", check_error_code=False)
        await self.cmd(f"setenv serverip {self._tftp_host}")
        await self.cmd(f"setenv tftpdstp {self._tftp_port}")
        # Increase block and window sizes to improve transfer speeds.
        # In practice, this improves transfer speeds tenfold. E.g.,
        # from ~1 MB/s to ~10 MB/s.
        await self.cmd("setenv tftpblocksize 1468")
        await self.cmd("setenv tftpwindowsize 256")
        # We exploit the "tftpboot" command and make it do arbitrary file transfers.
        # In order to do so, we disable the "boot" aspect of it with `autostart=no`.
        await self.cmd("setenv autostart no")
        self._initialized_network = True

    async def _start_tftp_server(self) -> None:
        """Start the TFTP server that we use to send data to the device."""
        self.logger.info("Start TFTP server")
        # Serves everything inside `TEMP_DIR`
        tftp_server = AsyncTFTPServer(
            self._tftp_host, self._tftp_port, directory=TEMP_DIR
        )
        assert self._stack is not None
        await self._stack.enter_async_context(tftp_server)

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

    async def _on_enter_pre_prompt(self) -> None:
        await self._dev.hard_restart()
