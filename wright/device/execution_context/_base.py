from __future__ import annotations

import warnings
from abc import abstractmethod
from logging import Logger
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Optional,
    Type,
    TypeVar,
    cast,
)

from anyio.abc import TaskGroup
from anyio.lowlevel import checkpoint

if TYPE_CHECKING:
    from .._device import Device


Derived = TypeVar("Derived", bound="Base")


class Base(AsyncContextManager["Base"]):
    """Base class for an execution context."""

    def __init__(self, device: "Device", tg: TaskGroup) -> None:
        self._dev = device
        self._tg = tg
        self._logger = device.logger
        self._entered = False
        self._exited = False

    @property
    def device(self) -> "Device":
        """Return the device used in this instance."""
        return self._dev

    @property
    def logger(self) -> Logger:
        """Return the logger used in this instance."""
        return self._logger

    @classmethod
    def is_entered(cls, device: "Device") -> bool:
        """Is the given device currently in an execution context of this type."""
        return device.metadata.execution_context is cls

    def _raise_if_not_entered(self) -> None:
        if not self._entered:
            raise RuntimeError("You must enter the execution environment first.")

    def _raise_if_exited(self) -> None:
        if self._exited:
            raise RuntimeError("You exited this context and can't use it anymore.")

    async def _boot_if_necessary(self) -> None:
        """Perform the boot sequence if the device is not already in this context."""
        # Early out if there is not reason to perform the boot sequence
        if self._should_skip_boot():
            self._logger.info(
                "Already in %s. We skip the usual boot sequence.",
                type(self).__name__,
            )
            await checkpoint()
            return
        # Boot. E.g., restart device, set kernel flags, and boot into the kernel
        await self._boot()

    def _should_skip_boot(self) -> bool:
        """Return hint about whether we should skip the boot sequence.

        E.g., if the device is already in an execution context of our type.
        This can save us from, e.g., the lengthy Linux boot sequence.
        """
        return type(self).is_entered(self.device)

    @abstractmethod
    async def _boot(self) -> None:
        """Take the initial step to enter this execution context.

        Usually, this restarts the device, sets some variables, etc.
        """
        ...

    async def __aenter__(self) -> Derived:
        self.device.metadata = self.device.metadata.update(execution_context=type(self))
        self._entered = True
        return cast(Derived, self)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._exited = True
        # Invalidate context if we exit with an error
        if exc_type is not None:
            self.device.metadata = self.device.metadata.update(execution_context=None)

    def __del__(self) -> None:
        if self._entered and not self._exited:
            message = f"Forgot to exit execution context: {self}"
            warnings.warn(message, category=ResourceWarning)
