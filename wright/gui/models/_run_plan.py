from __future__ import annotations

from ...model import FrozenModel
from ._run_parameters import RunParameters
from ._run_steps import RunSteps


class RunPlan(FrozenModel):
    parameters: RunParameters
    steps: RunSteps

    def with_next_pcb_id(self) -> RunPlan:
        return self.update(parameters=self.parameters.with_next_pcb_id())

    def with_default_steps(self) -> RunPlan:
        return self.update(steps=RunSteps())
