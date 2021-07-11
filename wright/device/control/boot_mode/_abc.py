from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractContextManager, contextmanager
from types import TracebackType
from typing import Iterator, Optional, Type

from ._boot_mode import BootMode


class AbstractBootModeControl(AbstractContextManager["AbstractBootModeControl"]):
    """ABC for boot mode control."""

    @property
    @abstractmethod
    def default_mode(self) -> BootMode:
        """Return the default boot mode.

        When used as a context manager, this class switches to the default
        mode on enter and exit.
        """
        ...

    @abstractmethod
    def get_mode(self) -> BootMode:
        """Return the current boot mode."""
        ...

    @abstractmethod
    def set_mode(self, value: BootMode) -> None:
        """Set the boot mode."""
        ...

    @contextmanager
    def scoped(self, value: BootMode) -> Iterator[None]:
        """Switch to the given boot mode while in the context manager."""
        previous_mode = self.get_mode()
        try:
            self.set_mode(value)
            yield
        finally:
            self.set_mode(previous_mode)

    def __enter__(self) -> AbstractBootModeControl:
        self.set_mode(self.default_mode)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.set_mode(self.default_mode)
