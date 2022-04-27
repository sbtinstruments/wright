from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import RunPlan
from ._run_plan_widget import RunPlanWidget

# Note that this is not a secure way to store a password. We don't care about
# security for this feature. It's merely a way to make a malicious use explicit.
_UNLOCK_PASSWORD = "banan"


class StartRunDialog(QDialog):
    """Form dialog to start a run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start run")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._run_plan_widget = RunPlanWidget(self)
        self._layout.addWidget(self._run_plan_widget)

        ### Messages
        self._messages = QPlainTextEdit(self)
        self._messages.setStyleSheet("color: red")
        self._messages.setReadOnly(True)
        self._layout.addWidget(self._messages)

        ### Buttons
        self._unlock_button = QPushButton(self)
        self._unlock_button.setText("Unlock settings...")
        self._layout.addWidget(self._unlock_button)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText("Cancel")
        self._layout.addWidget(self._cancel_button)

        self._start_run_button = QPushButton(self)
        self._start_run_button.setMinimumHeight(50)
        self._start_run_button.setText("Start run")
        self._start_run_button.setStyleSheet("background: blue;")
        self._layout.addWidget(self._start_run_button)

        ### Connections
        self._unlock_button.clicked.connect(self._open_unlock_dialog)
        self._cancel_button.clicked.connect(self.reject)
        self._start_run_button.clicked.connect(self.accept)

        ### Validation timer
        self._validation_timer = QTimer(self)
        self._validation_timer.setInterval(1000)
        self._validation_timer.timeout.connect(self._validate)
        self._validation_timer.start()
        # Initial validation (to avoid 1 second delay before the timer kicks in)
        self._validate()

    def model(self) -> RunPlan:
        return self._run_plan_widget.model()

    def _validate(self) -> None:
        try:
            model = self.model()
            # Try to construct the reset parameters. This exercises the deepest
            # validation chain.
            model.parameters.reset_params
            # Make sure that the files exist
            if not model.parameters.swu_file.is_file():
                raise ValueError("SWU path does not point a file that exists")
        except ValueError as exc:
            message = str(exc)
            # Only update on changes. This avoids selection reset.
            if self._messages.toPlainText() != message:
                self._messages.setPlainText(message)
            self._messages.setEnabled(True)
            self._start_run_button.setEnabled(False)
        else:
            self._messages.setPlainText("")
            self._messages.setEnabled(False)
            self._start_run_button.setEnabled(True)

    def setRunPlan(self, run_plan: RunPlan) -> None:
        self._run_plan_widget.setRunPlan(run_plan)
        self._validate()
        self._start_run_button.setFocus()

    def _open_unlock_dialog(self) -> None:
        dialog = UnlockDialog(self)
        if dialog.exec():
            self._run_plan_widget.unlock_all_settings()
            self._unlock_button.setEnabled(False)


class UnlockDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Unlock settings")
        self._layout = QFormLayout()
        self.setLayout(self._layout)

        self._password = QLineEdit(self)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._layout.addRow("Password", self._password)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText("Cancel")
        self._layout.addWidget(self._cancel_button)

        self._unlock_button = QPushButton(self)
        self._unlock_button.setText("Unlock")
        self._layout.addWidget(self._unlock_button)

        self._cancel_button.clicked.connect(self.reject)
        self._unlock_button.clicked.connect(self.accept)

        self._password.textChanged.connect(self._passwordChanged)

        # Initial refresh
        self._passwordChanged("")

    def _passwordChanged(self, password) -> None:
        accepted = password == _UNLOCK_PASSWORD
        self._unlock_button.setEnabled(accepted)
        self._unlock_button.setFocus()
