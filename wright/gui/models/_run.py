from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import Field

from ...device.models import ElecRef
from ...model import FrozenModel
from ._run_plan import RunPlan
from ._run_status import RunStatus

_BASE_FILE_NAME = "run_base.json"
_LOG_FILE_NAME = "log.html"


class RunBase(FrozenModel):
    status: RunStatus
    plan: RunPlan
    done_at: datetime = Field(default_factory=datetime.now)

    def with_next_pcb_id(self) -> Run:
        return self.update(plan=self.plan.with_next_pcb_id())

    def with_default_steps(self) -> Run:
        return self.update(plan=self.plan.with_default_steps())


class PartialRun(FrozenModel):
    base: RunBase
    # The directory contains files used to convert this partial run into a full run.
    directory: Path

    @classmethod
    def from_dir(cls, run_dir: Path) -> PartialRun:
        # Base
        base_file = run_dir / _BASE_FILE_NAME
        base = RunBase.parse_file(base_file)
        return cls(base=base, directory=run_dir)


class Run(FrozenModel):
    base: RunBase
    log: str  # HTML
    elec_ref: Optional[ElecRef] = None

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
            base=partial_run.base,
            log=log,
            elec_ref=elec_ref,
        )

    def directory(self, parent_dir: Path) -> Path:
        timestamp = self.base.done_at.isoformat().replace(":", "_")
        dir_name = f"{timestamp} {self.base.plan.parameters.hostname}"
        return parent_dir / dir_name

    def to_dir(self, parent_dir: Path) -> None:
        run_dir = self.directory(parent_dir)
        run_dir.mkdir()
        # Base
        base_file = run_dir / _BASE_FILE_NAME
        base_file.write_text(self.base.json())
        # Log
        log_file = run_dir / _LOG_FILE_NAME
        log_file.write_text(self.log)
        # Electronics reference
        if self.elec_ref is not None:
            self.elec_ref.save_in_dir(run_dir)

    def with_next_pcb_id(self) -> Run:
        return self.update(base=self.base.with_next_pcb_id())

    def with_default_steps(self) -> Run:
        return self.update(base=self.base.with_default_steps())
