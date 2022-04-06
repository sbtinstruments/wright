from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Union

from ..model import FrozenModel


class _IdleBase(FrozenModel):
    expected_duration: timedelta
    tries: int


class _RunningBase(_IdleBase):
    begin_at: datetime


class _CompletedBase(_RunningBase):
    end_at: datetime

    def run(self) -> Running:
        """Run the step again."""
        return Running(
            expected_duration=self.expected_duration,
            tries=self.tries + 1,
            begin_at=datetime.now(),
        )


class Skipped(_IdleBase):
    """Did not run the step."""

    status_type: Literal["skipped"] = "skipped"


class Completed(_CompletedBase):
    """Successfully completed the step without failure or cancellation."""

    status_type: Literal["completed"] = "completed"


class Cancelled(_CompletedBase):
    """The user or system cancelled the step.

    Either due to:
     * press CTRL+C
     * receive SIGTERM signal
     * etc.
    """

    status_type: Literal["cancelled"] = "cancelled"


class Failed(_CompletedBase):
    """The step failed due to an error."""

    status_type: Literal["failed"] = "failed"


class Running(_RunningBase):
    """The step currently runs."""

    status_type: Literal["running"] = "running"

    def cancel(self) -> Cancelled:
        """Cancel the step."""
        return Cancelled(
            expected_duration=self.expected_duration,
            tries=self.tries,
            begin_at=self.begin_at,
            end_at=datetime.now(),
        )

    def complete(self) -> Completed:
        """Mark that the step completed successfully (without error)."""
        return Completed(
            expected_duration=self.expected_duration,
            tries=self.tries,
            begin_at=self.begin_at,
            end_at=datetime.now(),
        )

    def fail(self) -> Failed:
        """Mark that the step failed with an error."""
        return Failed(
            expected_duration=self.expected_duration,
            tries=self.tries,
            begin_at=self.begin_at,
            end_at=datetime.now(),
        )


class Idle(_IdleBase):
    """The step is idle and waits for someone to run or skip it."""

    status_type: Literal["idle"] = "idle"

    def run(self) -> Running:
        """Run the step for the first time."""
        return Running(
            expected_duration=self.expected_duration, tries=1, begin_at=datetime.now()
        )

    def skip(self) -> Skipped:
        """Skip the step (mark that we did not run it)."""
        return Skipped(expected_duration=self.expected_duration, tries=0)


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
