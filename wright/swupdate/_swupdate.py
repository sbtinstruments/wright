from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Optional
from zlib import crc32

from ..device import DeviceType
from ..subprocess import run_process
from ..util import TEMP_DIR

_CPIO_EXE = "cpio"
_CHECKSUM_FILE_NAME = "swu-checksum"


@dataclass(frozen=True)
class DeviceBundle:
    """Combination of firmware and software update for a specific device."""

    firmware: Path
    software: Path


@dataclass(frozen=True)
class MultiBundle:
    """Collection of device-specific update bundles."""

    checksum: str
    device_bundles: dict[DeviceType, DeviceBundle]

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
        # Skip the extraction process if the fingerprint matches an
        # existing record.
        if not swu_dir.exists():
            await extract_swu(swu, swu_dir, logger=logger)
            store_checksum(swu, checksum_file)
        # Get checksum
        checksum = checksum_file.read_text()
        return cls(
            checksum,
            {
                DeviceType.BACTOBOX: DeviceBundle(
                    swu_dir / "bactobox-boot-with-u-boot-env.bin",
                    swu_dir / "bactobox-system.img",
                ),
                DeviceType.ZEUS: DeviceBundle(
                    swu_dir / "zeus-boot-with-u-boot-env.bin",
                    swu_dir / "zeus-system.img",
                ),
            },
        )


async def extract_swu(
    swu: Path, dest_dir: Path, *, logger: Optional[Logger] = None
) -> None:
    """Extract the SWU file contents to the current working directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    command = (_CPIO_EXE, "-idv")
    await run_process(
        command, stdin_file=swu, stdout_logger=logger, cwd=dest_dir.absolute()
    )


def store_checksum(swu: Path, checksum_file: Path) -> None:
    """Compute CRC32 checksum of `swu` and store it in `checksum_file`."""
    data = swu.read_bytes()
    checksum = crc32(data)
    checksum_file.write_text(str(checksum))
