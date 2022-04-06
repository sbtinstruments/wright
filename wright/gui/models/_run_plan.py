from __future__ import annotations

from ...model import FrozenModel
from ._run_parameters import RunParameters
from ._run_steps import RunSteps


class RunPlan(FrozenModel):
    parameters: RunParameters
    steps: RunSteps

    def with_next_hostname(self) -> RunPlan:
        return self.update(parameters=self.parameters.with_next_hostname())
