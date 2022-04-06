from typing import Optional

from PyQt5.QtWidgets import QVBoxLayout, QWidget

from ..models import RunParameters, RunPlan
from ._run_parameters_widget import RunParametersWidget
from ._run_steps_widget import RunStepsWidget


class RunPlanWidget(QWidget):
    """Plan (parameters and steps) of a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._run_parameters_widget = RunParametersWidget(self)
        self._layout.addWidget(self._run_parameters_widget)

        self._run_steps_widget = RunStepsWidget(self)
        self._run_steps_widget.setEnabled(False)
        self._layout.addWidget(self._run_steps_widget)

    def model(self) -> RunPlan:
        return RunPlan(
            parameters=self._run_parameters_widget.model(),
            steps=self._run_steps_widget.model(),
        )

    def setRunPlan(self, run_plan: RunPlan) -> None:
        self._run_parameters_widget.setModel(run_plan.parameters)
        self._run_steps_widget.setModel(run_plan.steps)

    def unlock_all_settings(self) -> None:
        self._run_parameters_widget.unlock_all_settings()
        self._run_steps_widget.setEnabled(True)
