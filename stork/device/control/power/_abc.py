from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Optional, Type


class AbstractPowerControl(AbstractContextManager["AbstractPowerControl"]):
    """ABC for power control."""

    @property
    @abstractmethod
    def default_state(self) -> bool:
        """Return the default state.

        When used as a context manager, this class switches to the default
        state on enter and exit.
        """
        ...

    @abstractmethod
    def get_state(self) -> bool:
        """Is the power on."""
        ...

    @abstractmethod
    def set_state(self, value: bool) -> None:
        """Turn the power on (True) or off (False)."""
        ...

    def __enter__(self) -> AbstractPowerControl:
        self.set_state(self.default_state)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.set_state(self.default_state)
