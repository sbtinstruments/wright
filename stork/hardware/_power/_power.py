from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Type


DEFAULT_POWER_ON = False


class PowerControl(ABC):
    @property
    @abstractmethod
    def on(self) -> bool:
        ...

    @on.setter
    @abstractmethod
    def on(self, value: bool) -> None:
        ...

    @abstractmethod
    def copy(self) -> PowerControl:
        ...

    def __enter__(self) -> PowerControl:
        self.on = DEFAULT_POWER_ON
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        self.on = DEFAULT_POWER_ON
