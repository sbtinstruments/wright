from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Union


@dataclass(frozen=True)
class _IdleBase:
    expected_duration: timedelta
    tries: int


@dataclass(frozen=True)
class _RunningBase(_IdleBase):
    begin_at: datetime


@dataclass(frozen=True)
class _CompletedBase(_RunningBase):
    end_at: datetime

    def run(self) -> Running:
        """Run the step again."""
        return Running(self.expected_duration, self.tries + 1, datetime.now())


@dataclass(frozen=True)
class Skipped(_IdleBase):
    """Did not run the step."""


@dataclass(frozen=True)
class Completed(_CompletedBase):
    """Successfully completed the step without failure or cancellation."""


@dataclass(frozen=True)
class Cancelled(_CompletedBase):
    """The user or system cancelled the step.

    Either due to:
     * press CTRL+C
     * receive SIGTERM signal
     * etc.
    """


@dataclass(frozen=True)
class Failed(_CompletedBase):
    """The step failed due to an error."""


@dataclass(frozen=True)
class Running(_RunningBase):
    """The step currently runs."""

    def cancel(self) -> Cancelled:
        """Cancel the step."""
        return Cancelled(
            self.expected_duration, self.tries, self.begin_at, datetime.now()
        )

    def complete(self) -> Completed:
        """Mark that the step completed successfully (without error)."""
        return Completed(
            self.expected_duration, self.tries, self.begin_at, datetime.now()
        )

    def fail(self) -> Failed:
        """Mark that the step failed with an error."""
        return Failed(self.expected_duration, self.tries, self.begin_at, datetime.now())


@dataclass(frozen=True)
class Idle(_IdleBase):
    """The step is idle and waits for someone to run or skip it."""

    def run(self) -> Running:
        """Run the step for the first time."""
        return Running(self.expected_duration, 1, datetime.now())

    def skip(self) -> Skipped:
        """Skip the step (mark that we did not run it)."""
        return Skipped(self.expected_duration, 0)


# State machine:
#
#   Idle --> Skipped
#     |
#     `----> Running --> Completed --> Running
#               |
#               |------> Cancelled --> Running
#               |
#               `------> Failed -----> Running
#
Status = Union[Idle, Skipped, Running, Completed, Cancelled, Failed]
