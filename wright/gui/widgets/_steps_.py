from pathlib import Path
from typing import Optional, cast

from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ...device.models import Branding
from ...device import DeviceType
from ..models import RunParameters


class StepsSettingsWidget(QWidget):
    """Setting of the steps in a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        ### Basic
        self._basic = QGroupBox(self)
        self._basic.setTitle("Basic settings")
        self._layout.addWidget(self._basic)
        self._basic_layout = QFormLayout()
        self._basic.setLayout(self._basic_layout)

        self._hw_version = QLineEdit(self)
        self._basic_layout.addRow("HW version", self._hw_version)

        self._pcb_id = QLineEdit(self)
        self._basic_layout.addRow("PCB identification number", self._pcb_id)

        ### Advanced
        self._advanced = QGroupBox(self)
        self._advanced.setTitle("Advanced settings")
        self._layout.addWidget(self._advanced)
        self._advanced_layout = QFormLayout()
        self._advanced.setLayout(self._advanced_layout)

        self._swu_file = QLineEdit(self)
        self._advanced_layout.addRow("SWU file", self._swu_file)

        self._device_type = QComboBox(self)
        for key, value in DeviceType.__members__.items():
            self._device_type.addItem(key, value)
        self._advanced_layout.addRow("Device type", self._device_type)

        self._branding = QComboBox(self)
        for key, value in Branding.__members__.items():
            self._branding.addItem(key, value)
        self._advanced_layout.addRow("Branding", self._branding)

    def model(self) -> RunParameters:
        device_type = cast(DeviceType, self._device_type.currentData())
        swu_file = Path(self._swu_file.text())  # TODO: Use device type in placeholder
        branding = cast(Branding, self._branding.currentData())
        return RunParameters(
            device_type=device_type,
            device_version=self._hw_version.text(),
            swu_file=swu_file,
            branding=branding,
            pcb_identification_number=self._pcb_id.text(),
        )

    def setModel(self, model: RunParameters) -> None:
        self._device_type.setCurrentText(model.device_type.name)
        self._hw_version.setText(model.device_version)
        self._swu_file.setText(str(model.swu_file))
        self._branding.setCurrentText(model.branding.name)
        if model.pcb_identification_number is not None:
            self._pcb_id.setText(model.pcb_identification_number)
        else:
            self._pcb_id.setText("")
