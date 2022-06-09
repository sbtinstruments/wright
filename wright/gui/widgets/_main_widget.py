import logging
from contextlib import contextmanager
from math import inf
from typing import Iterator

import anyio
from anyio.abc import TaskGroup
from anyio.streams.memory import MemoryObjectReceiveStream
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtWidgets import QGridLayout, QPushButton, QSizePolicy, QWidget

from ...progress import StatusMap, StatusStream
from ..globals import STORAGE_DIR
from ..models import PartialRun, Run, RunPlan, RunStatus, RunBase
from ._history_widget import HistoryWidget
from ._log_widget import GuiFormatter, GuiHandler
from ._outcome_widget import OutcomeWidget
from ._run_plan_widget import RunPlanWidget
from ._run_status_widget import RunStatusWidget
from .._start_run import start_run
from .._monitor_run import monitor_run_progress
from .._get_run_plan import get_run_plan

_LOGGER = logging.getLogger()  # root logger


class MainWidget(QWidget):
    """Root widget that contains all other widgets."""

    def __init__(self, tg: TaskGroup) -> None:
        super().__init__(None)
        self._tg = tg
        self._close_event = anyio.Event()
        self._layout = QGridLayout()
        self.setLayout(self._layout)

        self._history_widget = HistoryWidget(self)
        self._history_widget.setSizePolicy(
            QSizePolicy.Policy.Maximum,  # Do not grow beyond the size hint
            QSizePolicy.Policy.MinimumExpanding,
        )
        self._layout.addWidget(self._history_widget, 0, 0)

        self._run_plan_widget = RunPlanWidget(self)
        self._run_plan_widget.setEnabled(False)
        self._run_plan_widget.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Maximum,
        )
        self._layout.addWidget(self._run_plan_widget, 0, 1, Qt.AlignmentFlag.AlignTop)

        self._outcome_widget = OutcomeWidget(self)
        self._layout.addWidget(self._outcome_widget, 0, 2)

        self._start_run_button = QPushButton(self)
        self._start_run_button.setText("Begin...")
        self._start_run_button.setMinimumHeight(200)
        self._start_run_button.setStyleSheet("background: blue;")
        self._layout.addWidget(self._start_run_button, 1, 0)

        self._stop_run_button = QPushButton(self)
        self._stop_run_button.setText("Stop run")
        self._stop_run_button.setMinimumHeight(self._start_run_button.minimumHeight())
        self._stop_run_button.hide()
        self._stop_run_button.setStyleSheet("background: lightgray;")
        self._layout.addWidget(self._stop_run_button, 1, 0)

        self._run_status_widget = RunStatusWidget(self)
        self._layout.addWidget(self._run_status_widget, 1, 1, 1, 2)  # Span two columns

        self._start_run_button.setFocus()

        # Connections
        self._start_run_button.clicked.connect(self._plan_and_start_run)
        self._history_widget.runSelected.connect(self._show_run)

    async def waitClosed(self) -> None:
        """Return when this window is closed."""
        await self._close_event.wait()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Return:
            if self._start_run_button.isVisible():
                self._start_run_button.click()
                return
            elif self._stop_run_button.isVisible():
                self._stop_run_button.click()
                return
        return super().keyPressEvent(event)

    def closeEvent(self, _event: QCloseEvent) -> None:
        self._close_event.set()
        self._tg.cancel_scope.cancel()  # TODO: Consider to move this to a higher level

    def _show_run(self, partial_run: PartialRun) -> None:
        try:
            run = Run.from_partial_run(partial_run)
        except ValueError as exc:
            _LOGGER.warning(f"Could not parse run: {exc}")
            return
        self._run_plan_widget.setRunPlan(run.base.plan)
        self._outcome_widget.setLogHtml(run.log)
        self._outcome_widget.setElecRef(run.elec_ref)
        self._run_status_widget.setStatusMap(run.base.status)

    def _plan_and_start_run(self) -> None:
        run_plan = get_run_plan(self, self._history_widget)
        # Early out if we didn't get any settings (the user cancelled)
        if run_plan is None:
            return
        self._tg.start_soon(self._start_run, run_plan)

    async def _start_run(self, run_plan: RunPlan) -> None:
        # Progress
        progress_send_stream: StatusStream
        progress_receive_stream: MemoryObjectReceiveStream[StatusMap]
        (
            progress_send_stream,
            progress_receive_stream,
        ) = anyio.create_memory_object_stream(inf)
        # Start run tasks (the run itself and various progress/status tasks)
        run_cancel_scope = anyio.CancelScope()
        with self._run_mode(run_plan, run_cancel_scope):
            async with anyio.create_task_group() as run_tg:
                run_tg.start_soon(
                    start_run,
                    run_plan,
                    progress_send_stream,
                    run_cancel_scope,
                    self._outcome_widget,
                )
                run_tg.start_soon(
                    monitor_run_progress,
                    progress_receive_stream,
                    self._run_status_widget,
                )
        # Save run
        run = Run(
            base=RunBase(
                status=self._run_status_widget.statusMap(),
                plan=run_plan,
            ),
            log=self._outcome_widget.getLogHtml(),
            elec_ref=self._outcome_widget.getElecRef(),
        )
        run.to_dir(STORAGE_DIR)
        # Refresh run history
        self._history_widget.refresh()

    @contextmanager
    def _run_mode(
        self,
        run_plan: RunPlan,
        cancel_scope: anyio.CancelScope,
    ) -> Iterator[None]:
        try:
            # Reset UI
            self._outcome_widget.setLogHtml("")
            self._outcome_widget.setElecRef(None)
            self._run_plan_widget.setRunPlan(run_plan)
            self._run_status_widget.setStatusMap(RunStatus())
            # Lock inputs
            self._history_widget.setEnabled(False)
            # Toggle buttons
            self._start_run_button.setEnabled(False)
            self._start_run_button.hide()
            self._stop_run_button.setEnabled(True)
            self._stop_run_button.show()
            self._stop_run_button.setEnabled(True)
            self._stop_run_button.clicked.connect(cancel_scope.cancel)
            self._stop_run_button.clicked.connect(
                lambda: self._stop_run_button.setEnabled(False)
            )
            # Logging
            handler = GuiHandler(self._outcome_widget._log)
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(GuiFormatter())
            _LOGGER.addHandler(handler)
            yield
        finally:
            _LOGGER.removeHandler(handler)
            self._stop_run_button.setEnabled(False)
            self._stop_run_button.hide()
            self._start_run_button.setEnabled(True)
            self._start_run_button.show()
            self._history_widget.setEnabled(True)
