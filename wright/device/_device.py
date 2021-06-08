from __future__ import annotations

from abc import abstractmethod
from logging import Logger, getLogger
from typing import AsyncContextManager, Optional

from ._device_description import DeviceLink

_LOGGER = getLogger(__name__)


class Device(AsyncContextManager["Device"]):
    """Base class for a device connected to the host."""

    def __init__(self, link: DeviceLink, *, logger: Optional[Logger] = None):
        self._link = link
        self._logger = logger if logger is not None else _LOGGER

    @property
    def link(self) -> DeviceLink:
        """Return the means by which the host connects to this device."""
        return self._link

    @property
    def logger(self) -> Logger:
        """Return the logger associated with this device."""
        return self._logger

    async def hard_restart(self) -> None:
        """Restart this device via a power cycle."""
        self.logger.info("Restart device")
        await self.hard_power_off()
        self._power_on()

    @abstractmethod
    async def hard_power_off(self) -> None:
        """Turn this device off via a hard power cut."""
        ...

    @abstractmethod
    def _power_on(self) -> None:
        """Turn this device on."""
        ...
