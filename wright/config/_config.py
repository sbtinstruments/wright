import shutil
from importlib import resources
from logging import Logger
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..device import DeviceType
from ..subprocess import run_process
from ..util import TEMP_DIR
from .branding import Branding, assets

# TODO: Let's just use one of these and remove the rest.
_AUTHORIZED_KEYS = """
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIC9gjH94IkVLPkBF2YKbP56XSP4hOUr28IrkPzoC1kP1 frederikaalund@Frederiks-Air.lan
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIALb4+ULe7qRSKCQuaWYfEcdsgH+6QYMtakJUzvJXP+2 frederik@frederik-VirtualBox
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIO1tIn40FalyKAlSAmNLdq9kg4/RqnKsZkxyQvjlgO34 FPA@SBT-005
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBPlQL4qwXHE5qqJUed9yG+yqV5GCRULFgkp7OY5yn87 Frederik Aalund@DESKTOP-H5L6IRU
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKWCQDpcpbFZMDQ9w5QXZ92RmrPyAWd8GphWxMtlILQH SBT-Admin@DESKTOP-RQ3C127
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH+dVQEQaSaTT/mUNiN27bQvrC5yPdf0ujduI8Xt/5hB frederik@frederik-VirtualBox
""".lstrip()


async def create_config_image(
    dest: Path,
    *,
    device_type: DeviceType,
    device_version: str,
    branding: Branding,
    hostname: str,
    time_zone: Optional[str] = None,
    manufacturer: Optional[str] = None,
    logger: Optional[Logger] = None,
) -> None:
    """Create a config.img file in the current working directory."""
    # Default arguments
    if time_zone is None:
        time_zone = "Europe/Copenhagen"
    if manufacturer is None:
        manufacturer = "SBT Instruments A/S"

    # We need a directory to put all the files in before we can create
    # the IMG file.
    root = TEMP_DIR / "config"
    # Ensure that said directory is empty before we start filling it anew
    try:
        shutil.rmtree(root)
    except FileNotFoundError:
        pass
    root.mkdir()

    # Create files in the root directory
    create_file(root / "individual/root/.ssh/authorized_keys", _AUTHORIZED_KEYS)
    etc = root / "individual/etc"
    create_file(etc / "hostname", f"{hostname}\n")
    create_file(etc / "hosts", f"127.0.0.1 localhost\n127.0.1.1 {hostname}\n")
    create_file(etc / "timezone", f"{time_zone}\n")
    (etc / "localtime").symlink_to(f"/usr/share/zoneinfo/{time_zone}")
    create_ssh_key_pair(etc / "ssh")
    create_file(etc / "hwrevision", f"{device_type.value} {device_version}\n")
    create_file(etc / "hw-release", _hw_release(device_type, branding, manufacturer))
    create_splash_screen(root, branding)
    await create_image(root, dest, logger=logger)


async def create_image(
    directory: Path, dest: Path, *, logger: Optional[Logger] = None
) -> None:
    """Create an image with the contents from the given directory."""
    script = f"""\
		chown -Rh 0:0 {directory} && \
		chmod 700 {directory}/individual/root/.ssh && \
		chmod 600 {directory}/individual/root/.ssh/authorized_keys && \
        chmod 600 {directory}/individual/etc/ssh/ssh_host_ed25519_key && \
		mke2fs \
			-L "config" \
			-N 0 \
			-O 64bit \
			-d "{directory}" \
			-m 5 \
			-r 1 \
			-t ext4 \
			"{dest}" \
			100M
    """
    args = ["sh", "-c", script]
    await run_process(("fakeroot", *args), stdout_logger=logger, check_rc=True)


def create_file(path: Path, contents: Union[str, bytes]) -> None:
    """Create file at path with the given contents.

    Creates any missing directories in the path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if isinstance(contents, str) else "wb"
    with path.open(mode) as io:
        io.write(contents)


def create_ssh_key_pair(destination_dir: Path) -> None:
    """Create an SSH private/public key pair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    base_name = "ssh_host_ed25519_key"

    destination_dir.mkdir(parents=True, exist_ok=True)
    with (destination_dir / base_name).open("wb") as io:
        io.write(
            private_key.private_bytes(
                crypto_serialization.Encoding.PEM,
                crypto_serialization.PrivateFormat.OpenSSH,
                crypto_serialization.NoEncryption(),
            )
        )
    with (destination_dir / f"{base_name}.pub").open("wb") as io:
        io.write(
            public_key.public_bytes(
                crypto_serialization.Encoding.OpenSSH,
                crypto_serialization.PublicFormat.OpenSSH,
            )
        )


# The image formats supported by the secondary boot loader (U-boot
# in our case).
_IMAGE_FORMATS = [".bmp"]


def create_splash_screen(root: Path, branding: Branding) -> None:
    """Create a splash screen image according to the given branding."""
    graphics = root / "individual/etc/graphics"
    # Choose a splash screen in the first available image format
    chosen_format = _IMAGE_FORMATS[0]
    splash_screen = f"{branding.value}{chosen_format}"
    image = resources.read_binary(assets, splash_screen)
    create_file(graphics / f"splash{chosen_format}", image)
    # Symbolic links from the root to help the second-stage boot loader
    for image_format in _IMAGE_FORMATS:
        splash_from = root / f"splash{image_format}"
        splash_to = f"individual/etc/graphics/splash{image_format}"
        splash_from.symlink_to(splash_to)


_PRETTY_NAMES = {
    DeviceType.BACTOBOX: "BactoBox",
    DeviceType.ZEUS: "Zeus",
}


def _hw_release(device_type: DeviceType, branding: Branding, manufacturer: str) -> str:
    pretty_name = _PRETTY_NAMES[device_type]
    return (
        f'PRETTY_NAME="{pretty_name}"\n'
        f'MANUFACTURER="{manufacturer}"\n'
        f"BRANDING={branding.value}\n"
    )
