from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import Optional

from ..device import DeviceType
from ..subprocess import run_process

_CPIO_EXE = "cpio"


@dataclass(frozen=True)
class UpdateBundle:
    """Combination of firmware and software update."""

    firmware: Path
    software: Path


@dataclass(frozen=True)
class SwuFiles:
    """Device-specific update bundles."""

    devices: dict[DeviceType, UpdateBundle]

    @classmethod
    async def from_swu(
        cls,
        swu: Path,
        dest_dir: Path,
        logger: Optional[Logger] = None,
    ) -> SwuFiles:
        """Return an instance created from the given SWUpdate file."""
        # Use the stats (e.g., last modified) of the given SWU file as a fingerprint
        swu_stat = swu.stat()
        swu_fingerprint = hex(abs(hash(swu_stat)))[2:]
        swu_dir = dest_dir / f"{swu.name}__{swu_fingerprint}"
        # Skip the extraction process if the fingerprint matches an existing record
        if not swu_dir.exists():
            await extract_swu(swu, swu_dir, logger=logger)
        return cls(
            {
                DeviceType.BACTOBOX: UpdateBundle(
                    swu_dir / "bactobox-boot-with-u-boot-env.bin",
                    swu_dir / "bactobox-system.img",
                ),
                DeviceType.ZEUS: UpdateBundle(
                    swu_dir / "zeus-boot-with-u-boot-env.bin",
                    swu_dir / "zeus-system.img",
                ),
            }
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
