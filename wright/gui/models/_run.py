from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import Field

from ...device.models import ElecRef
from ...model import FrozenModel
from ._run_plan import RunPlan
from ._run_status import RunStatus

_STATUS_FILE_NAME = "status.json"
_PLAN_FILE_NAME = "plan.json"
_LOG_FILE_NAME = "log.html"


class PartialRun(FrozenModel):
    directory: Path
    status: RunStatus
    plan: RunPlan

    @property
    def done_at(self) -> datetime:
        try:
            return datetime.fromisoformat(self.directory.name.replace("_", ":"))
        except ValueError as exc:
            raise ValueError("Could not deconde done time from directory name") from exc

    @classmethod
    def from_dir(cls, run_dir: Path) -> PartialRun:
        # Status map
        status_file = run_dir / _STATUS_FILE_NAME
        status = RunStatus.parse_file(status_file)
        # Plan
        plan_file = run_dir / _PLAN_FILE_NAME
        plan = RunPlan.parse_file(plan_file)
        return cls(directory=run_dir, status=status, plan=plan)


class Run(FrozenModel):
    status: RunStatus
    plan: RunPlan
    log: str  # HTML
    elec_ref: Optional[ElecRef] = None
    done_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_partial_run(cls, partial_run: PartialRun) -> Run:
        # Log
        log_file = partial_run.directory / _LOG_FILE_NAME
        log = log_file.read_text()
        # Electronics reference
        elec_ref: Optional[ElecRef]
        try:
            elec_ref = ElecRef.load_from_dir(partial_run.directory)
        except OSError:
            elec_ref = None
        # Construct instance
        return cls(
            status=partial_run.status,
            plan=partial_run.plan,
            log=log,
            elec_ref=elec_ref,
            done_at=partial_run.done_at,
        )

    def directory(self, parent_dir: Path) -> Path:
        return parent_dir / self.done_at.isoformat().replace(":", "_")

    def to_dir(self, parent_dir: Path) -> None:
        run_dir = self.directory(parent_dir)
        run_dir.mkdir()
        # Status map
        status_file = run_dir / _STATUS_FILE_NAME
        status_file.write_text(self.status.json())
        # Plan
        plan_file = run_dir / _PLAN_FILE_NAME
        plan_file.write_text(self.plan.json())
        # Log
        log_file = run_dir / _LOG_FILE_NAME
        log_file.write_text(self.log)
        # Electronics reference
        if self.elec_ref is not None:
            self.elec_ref.save_in_dir(run_dir)

    def with_next_hostname(self) -> Run:
        return self.update(plan=self.plan.with_next_hostname())

    def with_default_steps(self) -> Run:
        return self.update(plan=self.plan.with_default_steps())
