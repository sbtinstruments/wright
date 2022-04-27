from __future__ import annotations

import gzip
from logging import Logger
from pathlib import Path
from typing import Any, Optional
from zlib import crc32

import anyio
import libconf
from anyio.to_thread import run_sync

from ..model import FrozenModel
from ..subprocess import run_process
from ..util import TEMP_DIR

_CPIO_EXE = "cpio"
_CHECKSUM_FILE_NAME = "swu-checksum"


class DiskImage(FrozenModel):
    """Image file and version used in a software update."""

    file: Path
    version: str


class DeviceBundle(FrozenModel):
    """Combination of firmware and operating system update for a specific device."""

    firmware: DiskImage
    operating_system: DiskImage


class MultiBundle(FrozenModel):
    """Collection of device-specific update bundles."""

    checksum: str
    # Mapping of device type (given as a string) to device bundle
    device_bundles: dict[str, DeviceBundle]

    @classmethod
    async def from_swu(
        cls,
        swu: Path,
        dest_dir: Optional[Path] = None,
        *,
        logger: Optional[Logger] = None,
    ) -> MultiBundle:
        """Return an instance created from the given SWUpdate file."""
        # TODO: We call this function from different processes.
        # E.g.: hilt, wright CLI, and wright GUI. Therefore, there is a
        # race condition between these processes and the `swu_dir` cache.
        # Either move to a proper cache mechanism or use some kind of
        # file system-level lock. Maybe a simple lock file will do.
        if dest_dir is None:
            dest_dir = TEMP_DIR
        # Use the stats (e.g., last modified) of the given SWU file as a
        # fingerprint. We prefer this `stat`-based approach over, e.g.,
        # a CRC32 checksum since the former is a lot faster.
        swu_stat = swu.stat()
        swu_fingerprint = hex(abs(hash(swu_stat)))[2:]
        swu_dir = dest_dir / f"{swu.name}__{swu_fingerprint}"
        checksum_file = swu_dir / _CHECKSUM_FILE_NAME
        sw_description_file = swu_dir / "sw-description"
        # Skip the extraction process if the fingerprint matches an
        # existing record.
        if not swu_dir.exists():
            await extract_swu(swu, swu_dir, logger=logger)
            await decompress_files(swu_dir, logger=logger)
            store_checksum(swu, checksum_file)
        # Get device bundles
        device_bundles = await get_device_bundles(sw_description_file)
        # Get checksum
        checksum = checksum_file.read_text()
        return cls(checksum=checksum, device_bundles=device_bundles)


async def extract_swu(
    swu: Path, dest_dir: Path, *, logger: Optional[Logger] = None
) -> None:
    """Extract the SWU file contents to the current working directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    command = (_CPIO_EXE, "-idv")
    await run_process(
        command, stdin_file=swu, stdout_logger=logger, cwd=dest_dir.absolute()
    )


async def decompress_files(
    directory: Path,
    *,
    chunk_size: Optional[int] = None,
    logger: Optional[Logger] = None,
) -> None:
    """Decompress all `.gz` files in the given directory (if any).

    Does not recurse into subfolders.

    This creates a new file next to the compressed file.
    """
    if chunk_size is None:
        chunk_size = 2 ** 20  # 1 MiB
    gz_files = (gz_file for gz_file in directory.glob("*.gz") if gz_file.is_file())
    async with anyio.create_task_group() as tg:
        for gz_file in gz_files:
            if logger is not None:
                logger.debug(f"Decompress {gz_file}")
            tg.start_soon(_decompress_file, gz_file, chunk_size, logger)


async def _decompress_file(*args: Any) -> None:
    await run_sync(_decompress_file, *args)


def _decompress_file_sync(
    gz_file: Path,
    chunk_size: int,
    logger: Logger,
) -> None:
    uncompressed = gz_file.with_suffix("")
    logger.debug(f"{uncompressed=}")
    if uncompressed.exists():
        logger.warning(
            f"The file {uncompressed} already exists. "
            f"We override it with the decompressed contents of {gz_file}."
        )
    with gzip.open(gz_file, "rb") as io_in, uncompressed.open(mode="wb") as io_out:
        while chunk := io_in.read(chunk_size):
            io_out.write(chunk)


async def get_device_bundles(sw_description_file: Path) -> dict[str, DeviceBundle]:
    """Get firmware and operating system dvice bundles from the description file."""
    swu_dir = sw_description_file.parent
    # Load in the libconfig-encoded description file
    with sw_description_file.open("rt") as io:
        sw_description = libconf.load(io)
    # Extract device bundles from the description
    software = sw_description["software"]
    # Get all device descriptions. This filters out the top-level entries such as
    # "version" and "description". All there is left is something like:
    #
    #   {"zeus": {...}, "bactobox": {...}}
    device_descriptions: dict[str, dict[str, Any]] = {
        device_type: description
        for device_type, description in software.items()
        if "stable" in description
    }
    # Convert from the description structure to our own bundle structure
    raw_device_bundles: dict[str, dict[str, DiskImage]] = {}
    # We would like to use two nested dict comprehensions. Unfortunately,
    # that is not possible since the inner comprehension is async.
    # See: https://stackoverflow.com/a/60042806/554283
    for device_type, description in device_descriptions.items():
        raw_device_bundles[device_type] = {
            # Convert, e.g., "operating-system" to "operating_system"
            image["name"].replace("-", "_"): await run_sync(
                _parse_image, image, swu_dir, cancellable=True
            )
            # This assumes a dual-copy strategy
            for image in description["stable"]["system0"]["images"]
        }
    # Finally, convert the raw dicts into `DeviceBundle` instances
    return {
        device_type: DeviceBundle(**raw_device_bundle)
        for device_type, raw_device_bundle in raw_device_bundles.items()
    }


def _parse_image(image: dict[str, str], directory: Path) -> DiskImage:
    """Create a `DiskImage` based on the given image dict."""
    filename = image["filename"]
    file = directory / filename
    # If there is a decompressed version of the file, prefer that over the
    # compressed version.
    if file.suffix == ".gz":
        uncompressed = file.with_suffix("")
        if uncompressed.is_file():
            file = uncompressed
    return DiskImage(file=file, version=image["version"])


def store_checksum(swu: Path, checksum_file: Path) -> None:
    """Compute CRC32 checksum of `swu` and store it in `checksum_file`."""
    data = swu.read_bytes()
    checksum = crc32(data)
    checksum_file.write_text(str(checksum))
