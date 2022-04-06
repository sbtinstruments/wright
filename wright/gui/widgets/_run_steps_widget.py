from pathlib import Path
from typing import Optional, cast

from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import RunSteps


class RunStepsWidget(QWidget):
    """Steps for a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._basic = QGroupBox(self)
        self._basic.setTitle("Steps")
        self._layout.addWidget(self._basic)
        self._basic_layout = QFormLayout()
        self._basic.setLayout(self._basic_layout)

        self._reset_firmware = QCheckBox(self)
        self._basic_layout.addRow("Reset firmware", self._reset_firmware)

        self._reset_operating_system = QCheckBox(self)
        self._basic_layout.addRow("Reset OS", self._reset_operating_system)

        self._reset_config = QCheckBox(self)
        self._basic_layout.addRow("Reset config", self._reset_config)

        self._reset_data = QCheckBox(self)
        self._basic_layout.addRow("Reset data", self._reset_data)

        self._set_electronics = QCheckBox(self)
        self._basic_layout.addRow("Set electronics reference", self._set_electronics)

    def model(self) -> RunSteps:
        return RunSteps(
            reset_firmware=self._reset_firmware.isChecked(),
            reset_operating_system=self._reset_operating_system.isChecked(),
            reset_config=self._reset_config.isChecked(),
            reset_data=self._reset_data.isChecked(),
            set_electronics_reference=self._set_electronics.isChecked(),
        )

    def setModel(self, model: RunSteps) -> None:
        self._reset_firmware.setChecked(model.reset_firmware)
        self._reset_operating_system.setChecked(model.reset_operating_system)
        self._reset_config.setChecked(model.reset_config)
        self._reset_data.setChecked(model.reset_data)
        self._set_electronics.setChecked(model.set_electronics_reference)
