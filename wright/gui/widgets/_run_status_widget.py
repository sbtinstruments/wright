from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFormLayout, QHBoxLayout, QLineEdit, QProgressBar, QWidget

from ..models import RunStatus, StepStatus


class RunStatusWidget(QWidget):
    """Status of a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout()
        self.setLayout(self._layout)

        self._prepare_status = StatusWidget(self)
        self._layout.addRow("Prepare", self._prepare_status)

        self._reset_firmware_status = StatusWidget(self)
        self._layout.addRow("Reset firmware", self._reset_firmware_status)

        self._reset_operating_system_status = StatusWidget(self)
        self._layout.addRow("Reset OS", self._reset_operating_system_status)

        self._reset_config_status = StatusWidget(self)
        self._layout.addRow("Reset config", self._reset_config_status)

        self._reset_data_status = StatusWidget(self)
        self._layout.addRow("Reset data", self._reset_data_status)

        self._set_electronics_reference = StatusWidget(self)
        self._layout.addRow(
            "Set electronics reference", self._set_electronics_reference
        )

        self._status_widgets: dict[str, StatusWidget] = {
            "prepare": self._prepare_status,
            "reset_firmware": self._reset_firmware_status,
            "reset_operating_system": self._reset_operating_system_status,
            "reset_config": self._reset_config_status,
            "reset_data": self._reset_data_status,
            "set_electronics_reference": self._set_electronics_reference,
        }

    def statusMap(self) -> RunStatus:
        steps = {
            name: w.status()
            for name, w in self._status_widgets.items()
            if w.status() is not None
        }
        return RunStatus(steps=steps)

    def setStatusMap(self, status_map: RunStatus) -> None:
        for name, status in status_map.steps.items():
            try:
                status_widget = self._status_widgets[name]
            except KeyError:
                continue
            status_widget.setStatus(status)


class StatusWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._step_status: Optional[StepStatus] = None
        self._layout = QHBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._progress = QProgressBar(self)
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._layout.addWidget(self._progress, 2)

        self._description = QLineEdit(self)
        self._description.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._description.setReadOnly(True)
        self._description.setMinimumWidth(200)
        self._layout.addWidget(self._description)

    def status(self) -> Optional[StepStatus]:
        return self._step_status

    def setStatus(self, status: StepStatus) -> None:
        self._step_status = status
        self._progress.setValue(status.progress)
        self._description.setText(status.description)
