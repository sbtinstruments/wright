from __future__ import annotations

from enum import Enum, unique

from pydantic import Extra

from ...model import FrozenModel


@unique
class BbpState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_done(self) -> bool:
        """Is the given state either completed, failed, or cancelled."""
        return self in (BbpState.COMPLETED, BbpState.FAILED, BbpState.CANCELLED)


class PartialBbpStatus(FrozenModel):
    state: BbpState

    class Config:
        extra = Extra.ignore  # This is a partial model


class Process(FrozenModel):
    """Process summary as given back by `psutil`."""

    name: str
    cmdline: tuple[str, ...]
