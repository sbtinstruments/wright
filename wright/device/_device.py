from __future__ import annotations

from abc import abstractmethod
from logging import Logger, getLogger
from typing import Any, AsyncContextManager, ContextManager, Optional

from ._device_description import DeviceDescription
from ._device_link import DeviceLink
from ._device_metadata import DeviceMetadata
from ._device_registry import get_device
from ._device_type import DeviceType
from .control.boot_mode import BootMode

_LOGGER = getLogger(__name__)


class Device(AsyncContextManager["Device"]):
    """Base class for a device connected to the host."""

    def __init__(
        self,
        version: str,
        link: DeviceLink,
        metadata: Optional[DeviceMetadata] = None,
        *,
        logger: Optional[Logger] = None,
    ):
        # Defaults
        if metadata is None:
            metadata = DeviceMetadata()
        self._version = version
        self._link = link
        # It's not the responsibility of this class to keep track of the metadata. It's
        # up to the user to manage the metadata. E.g., the current execution context
        # We simply provde the `metadata` variable as a convenience to help the user
        # keep track.
        # This class does, however, does somtime change the metadata for convenience.
        # E.g., to set the `execution_context` to `None` on power off.
        self.metadata = metadata
        # Automatically determine the device type
        self._device_type = _get_device_type(self)
        self._logger = logger if logger is not None else _LOGGER

    @property
    def version(self) -> str:
        """Return the version of this device."""
        return self._version

    @property
    def link(self) -> DeviceLink:
        """Return the means by which the host connects to this device."""
        return self._link

    @property
    def device_type(self) -> DeviceType:
        """Return the device type."""
        return self._device_type

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
        # Clear the execution context
        self.metadata = self.metadata.update(execution_context=None)

    @abstractmethod
    def _power_on(self) -> None:
        """Turn this device on."""
        ...

    @abstractmethod
    def scoped_boot_mode(self, value: BootMode) -> ContextManager[None]:
        """Switch to the given boot mode while in the context manager."""
        ...

    def description(self) -> DeviceDescription:
        """Return description of this device."""
        return DeviceDescription(
            device_type=self.device_type,
            device_version=self._version,
            link=self.link,
            metadata=self.metadata,
        )

    @staticmethod
    def from_description(description: DeviceDescription, **kwargs: Any) -> Device:
        """Return device instance based on the description."""
        device_cls = get_device(description.device_type.value)
        if device_cls is None:
            raise ValueError(
                f'No device registered for type: "{description.device_type}"'
            )
        return device_cls(
            description.device_version,
            description.link,
            description.metadata,
            **kwargs,
        )


def _get_device_type(device: Device) -> DeviceType:
    device_type_name = type(device).__name__.lower()
    try:
        return next(dt for dt in DeviceType if dt.value == device_type_name)
    except StopIteration as exc:
        raise RuntimeError(f'Unknown device type: "{device_type_name}"') from exc
