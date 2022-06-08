from typing import Optional

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from ...device import DeviceType
from ...device.models import ElecRef
from ._log_widget import LogWidget


class OutcomeWidget(QWidget):
    """Data and log (messages) of a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._tabs = QTabWidget(self)
        self._layout.addWidget(self._tabs)

        self._log = LogWidget(self)
        self._tabs.addTab(self._log, "Log")

        self._elec_ref: Optional[ElecRef] = None
        self._elec_ref_label = QLabel(self)
        self._tabs.addTab(self._elec_ref_label, "Electronics reference")
        self._tabs.setTabEnabled(1, False)
        self._tabs.setCurrentIndex(0)

    def setLogHtml(self, html: str) -> None:
        self._log.setHtml(html)

    def appendLogHtml(self, html: str) -> None:
        self._log.appendHtml(html)

    def getLogHtml(self) -> str:
        return self._log.toHtml()

    def getElecRef(self) -> Optional[ElecRef]:
        return self._elec_ref

    def setElecRef(self, elec_ref: Optional[ElecRef]) -> None:
        self._elec_ref = elec_ref
        if self._elec_ref is None or self._elec_ref.image_file is None:
            self._tabs.setTabEnabled(1, False)
            self._tabs.setCurrentIndex(0)
            return
        pixmap = QPixmap(str(self._elec_ref.image_file))
        self._elec_ref_label.setPixmap(pixmap)
        self._tabs.setTabEnabled(1, True)
        self._tabs.setCurrentIndex(1)
