from __future__ import annotations

from types import TracebackType
from typing import Type
from enum import Enum, auto
from abc import ABC, abstractmethod
from contextlib import contextmanager


class BootMode(Enum):
    JTAG = auto()
    QSPI = auto()


DEFAULT_BOOT_MODE = BootMode.QSPI


class BootModeControl(ABC):
    @property
    @abstractmethod
    def mode(self) -> BootMode:
        ...

    @mode.setter
    @abstractmethod
    def mode(self, value: BootMode) -> None:
        ...

    @abstractmethod
    def copy(self) -> BootModeControl:
        ...

    @contextmanager
    def scoped(self, value: BootMode) -> None:
        previous_mode = self.mode
        try:
            self.mode = value
            yield
        finally:
            self.mode = previous_mode

    def __enter__(self) -> BootModeControl:
        self.mode = DEFAULT_BOOT_MODE
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        self.mode = DEFAULT_BOOT_MODE
