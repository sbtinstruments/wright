from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum, unique
from typing import Iterable, Mapping

from pydantic import Field

from ...model import FrozenModel
from ...progress import (
    Cancelled,
    Completed,
    Failed,
    Idle,
    Running,
    Skipped,
    Status,
    StatusMap,
)


@unique
class OverallStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @staticmethod
    def from_statuses(statuses: Iterable[Status]) -> OverallStatus:
        # We make multiple passes over `statuses` for now. Therefore,
        # we convert it to a set first.
        # TODO: Use a single-pass implementation instead.
        statuses = set(statuses)
        # Early out if empty
        if not statuses:
            return OverallStatus.IDLE
        if any(isinstance(s, Cancelled) for s in statuses):
            return OverallStatus.CANCELLED
        if any(isinstance(s, Failed) for s in statuses):
            return OverallStatus.FAILED
        if all(isinstance(s, Completed) for s in statuses):
            return OverallStatus.COMPLETED
        if all(isinstance(s, Idle) for s in statuses):
            return OverallStatus.IDLE
        return OverallStatus.RUNNING


class StepStatus(FrozenModel):
    progress_status: Status
    evaluated_at: datetime

    @property
    def elapsed(self) -> timedelta:
        if isinstance(self.progress_status, (Idle, Skipped)):
            raise RuntimeError("Idle and skipped status does not have elapsed time")
        now = self.evaluated_at
        return now - self.progress_status.begin_at

    @property
    def progress(self) -> int:
        if isinstance(self.progress_status, Completed):
            return 100
        if isinstance(self.progress_status, Running):
            return int(self.elapsed / self.progress_status.expected_duration * 100)
        return 0

    @property
    def description(self) -> str:
        if isinstance(self.progress_status, Idle):
            return "Pending"
        if isinstance(self.progress_status, Skipped):
            return "Skipped"
        if isinstance(self.progress_status, Completed):
            description = "Completed"
            if self.progress_status.tries > 1:
                description += f" (tries: {self.progress_status.tries})"
            return description
        if isinstance(self.progress_status, Failed):
            return "Failed"
        if isinstance(self.progress_status, Cancelled):
            return "Cancelled"
        remaining = self.progress_status.expected_duration - self.elapsed
        description = f"Max {int(remaining.total_seconds())} seconds left"
        if self.progress_status.tries > 1:
            description += f" (tries: {self.progress_status.tries})"
        return description


class RunStatus(FrozenModel):
    steps: Mapping[str, StepStatus] = Field(default_factory=dict)

    @property
    def overall(self) -> OverallStatus:
        return OverallStatus.from_statuses(
            s.progress_status for s in self.steps.values()
        )

    @classmethod
    def from_progress_status_map(cls, status_map: StatusMap) -> RunStatus:
        now = datetime.now()
        return cls(
            steps={
                key: StepStatus(progress_status=s, evaluated_at=now)
                for key, s in status_map.items()
            }
        )
