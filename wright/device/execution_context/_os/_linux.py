from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..._device_condition import DeviceCondition
from .._deteriorate import deteriorate
from .._serial_base import SerialBase


class Linux(SerialBase, ABC):
    """Base class for Linux-based execution contexts."""

    @deteriorate(DeviceCondition.USED)
    async def reset_data(self) -> None:
        """Remove all data on this device."""
        await self.unbock_data_partition()
        await self.format_data_partition()

    @abstractmethod
    async def unbock_data_partition(self) -> None:
        """Stop all processes/mounts that may use the data partition."""
        ...

    @deteriorate(DeviceCondition.USED)
    async def format_data_partition(self) -> None:
        """Format the data partition.

        This deletes all data.
        """
        self.logger.info("Format data partition of MMC memory")
        # The umount command will fail if the data partition is invalid
        # or non-existing. Therefore, we skip the error code check.
        await self.cmd("umount /media/data", check_error_code=False)
        await self.cmd("yes | mkfs.ext4 -L data /dev/mmcblk0p4")

    @deteriorate(DeviceCondition.AS_NEW)
    async def get_date(self) -> datetime:
        """Return the device date."""
        date_str = await self.cmd("date +%s")
        assert date_str is not None
        return datetime.utcfromtimestamp(int(date_str))

    @deteriorate(DeviceCondition.AS_NEW)
    async def get_versions(self) -> dict[str, str]:
        """Return the versions of all installed firmware, software, etc."""
        raw_versions = await self.cmd("cat /etc/sw-versions")
        assert raw_versions is not None
        result: dict[str, str] = dict()
        lines = raw_versions.split("\n")
        for line in lines:  # Example `line`: "firmware 3.2.0"
            words = line.strip().split(" ")  # Example `words`: ["firmware", "3.2.0"]
            # Skip invalid lines
            if len(words) != 2:
                continue
            result[words[0]] = words[1]
        return result

    @deteriorate(DeviceCondition.AS_NEW)
    async def py(self, py_code: str) -> Optional[str]:
        """Run the given python code and return the result."""
        return await self.cmd(f'python -c "{py_code}"')
