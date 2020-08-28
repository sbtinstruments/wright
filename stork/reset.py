import logging
from datetime import datetime
from pathlib import Path

from .console import Console, Mode
from .flash import program_flash
from .hardware import Hardware
from .tftp import AsyncTFTPServer

_LOGGER = logging.getLogger(__name__)


def print_info(text):
    print("\033[7m>>>   " + text + "\033[0m")


async def press_enter_to_continue():
    print_info("Press <Enter> to continue")
    input()


async def _reset_hw(
    swu: Path,
    *,
    hardware: Hardware,
    hostname: str,
    tty: Path,
    tftp_host: str,
    tftp_port: int,
    skip_program_flash: bool,
    skip_system_image: bool,
    skip_config_image: bool,
    restore_default_uboot_env: bool,
):
    _LOGGER.info(f'Using TTY "{tty}"')
    tftp_server = AsyncTFTPServer(tftp_host, tftp_port, "./")
    console = Console(tty, hardware=hardware, hostname=hostname)
    async with tftp_server, console:
        print_info("Bring-up process started")
        if not skip_program_flash:
            print_info("Ensure that:")
            print_info("  1. The hardware is connected via:")
            print_info("     a) JTAG")
            print_info("     b) Serial")
            print_info("     c) Ethernet (e.g., via a USB-to-ethernet adapter)")
            print_info("  2. The 2-pin jumper is inserted")
            print_info("  3. The hardware is powered up")
            await press_enter_to_continue()
            start = datetime.now()
            print_info("Programming FLASH")
            program_flash(hardware.value)
            print_info("FLASH was successully programmed")
        else:
            print_info("Skipping FLASH programming")
            start = datetime.now()

        print_info("Do the following:")
        print_info("  1. Power off the hardware")
        print_info("  2. Remove the 2-pin jumper")
        print_info("  3. Power on the hardware")
        await console.force_prompt()

        if restore_default_uboot_env:
            # Hardware that has been previously brought up may have it's U-boot
            # environment left lingering in the FLASH memory. We reset it to
            # the default U-boot environment (the compiled-in one).
            print_info("Restoring the default U-boot environment (if any)")
            uboot_env_base = 15 * 1024 * 1024  # 15 MiB
            uboot_env_len = 2 * 64 * 1024  # 2 erase blocks of 64 KiB
            await console.cmd(f"env default -a")
            await console.cmd(f"sf probe")
            await console.cmd(f"sf erase {uboot_env_base:x} {uboot_env_len:x}")
            await console.cmd(f"saveenv")
            print_info("Resetting the hardware")
            await console.reset()
            await console.force_prompt()

        print_info("Partitioning the MMC memory")
        await console.cmd(
            'gpt write mmc 0 "name=system0,size=150MiB;name=system1,size=150MiB;name=config,size=100MiB;name=data,size=0"'
        )
        print_info("Resetting hardware")
        await console.reset()
        await console.force_prompt()

        print_info("Initializing network connection to the hardware")
        await console.cmd("usb start")
        await console.cmd("dhcp", check_error_code=False)
        await console.cmd(f"setenv serverip {tftp_host}")
        await console.cmd(f"setenv tftpdstp {tftp_port}")
        await console.cmd("setenv autostart no")

        if not skip_system_image:
            image = f"{hardware.value}-system.img"

            print_info(f"Transfer {image} to the hardware")
            await console.cmd(f"tftpboot 0x6000000 {image}")
            print_info(f"Write {image} to the MMC memory")
            # Writes system image (from DDR RAM) to partition "system0".
            # Note that the sector size is 512 byes (0x200). Therefore, we
            # write 0x4B000=0x9600000/0x200 sectors (i.e., 307200=150MiB/512B).
            await console.cmd("mmc write 0x6000000 0x00022 0x4B000")
            # Also write system image to partition "system1".
            await console.cmd("mmc write 0x6000000 0x4b022 0x4B000")

        if not skip_config_image:
            print_info("Transfer config.img to the hardware")
            await console.cmd("tftpboot 0x6000000 config.img")
            print_info("Write config.img to the MMC memory")
            await console.cmd("mmc write 0x6000000 0x96022 0x32000")

        await console.reset()
        print_info("The hardware will now reset and boot into Linux")
        await console.force_prompt()
        # Disable kernel logging as it messes with the serial output.
        # That is, sometimes the kernel will spam the serial line with
        # driver info messages. Said messages interfere with how we parse
        # the serial line.
        await console.cmd("setenv bootargs loglevel=0")
        await console.cmd("boot", wait_for_prompt=False)

        # Switch to Linux mode
        await console.set_mode(Mode.LINUX)
        await console.wait_for_prompt()
        print_info('Kill any "sleep"-delayed startup scripts')
        # We stop all the services that may be using the /media/data path.
        # Kill any delayed scripts first.
        await console.cmd("kill `ps | awk '/[s]leep/ {print $1}'`")
        print_info("Stop all processes that may use the data partition")
        await console.cmd("/etc/init.d/Amonit stop")
        await console.cmd("/etc/init.d/Adash stop")
        await console.cmd("/etc/init.d/Acellmate stop")
        await console.cmd("/etc/init.d/Abaxter stop")
        await console.cmd("/etc/init.d/Amester stop")
        await console.cmd("/etc/init.d/Amaskin stop")
        await console.cmd("/etc/init.d/S51rsyslog stop")
        await console.cmd("/etc/init.d/S70swupdate stop")
        # We use an 'awk'-based kill command to make sure that even
        # launching processes are killed as well.
        await console.cmd("kill `ps | awk '/[t]elegraf/ {print $1}'`")
        await console.cmd("kill `ps | awk '/[i]nfluxd/ {print $1}'`")
        print_info("Format the data partition of the MMC memory")
        # The umount command will fail if the data partition is invalid
        # or non-existing. Therefore, we skip the error code check.
        await console.cmd("umount /media/data", check_error_code=False)
        await console.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")
        print_info("The hardware will now power off")
        await console.cmd("poweroff")
        end = datetime.now()
        delta = end - start
        print_info(f"Bring-up successful (took {delta})")
