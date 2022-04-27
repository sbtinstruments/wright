import logging
from contextlib import contextmanager
from html import escape as escape_html
from math import inf
from traceback import format_exc
from typing import Iterator, Optional

import anyio
from anyio.abc import TaskGroup
from anyio.streams.memory import MemoryObjectReceiveStream
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtWidgets import QGridLayout, QPushButton, QSizePolicy, QWidget

from ...commands import (
    RESET_DEVICE_STATUS_MAP,
    SET_ELECTRONICS_REFERENCE_STATUS_MAP,
    reset_device,
    set_electronics_reference,
)
from ...device import Device
from ...progress import ProgressManager, StatusMap, StatusStream
from ..globals import _STORAGE_DIR
from ..models import ElecRef, OverallStatus, PartialRun, Run, RunPlan, RunStatus
from ._history_widget import HistoryWidget
from ._log_widget import GuiFormatter, GuiHandler
from ._outcome_widget import OutcomeWidget
from ._run_plan_widget import RunPlanWidget
from ._run_status_widget import RunStatusWidget
from ._start_run_dialog import StartRunDialog

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
        self._start_run_button.setMinimumHeight(170)
        self._start_run_button.setStyleSheet("background: blue;")
        self._layout.addWidget(self._start_run_button, 1, 0)

        self._stop_run_button = QPushButton(self)
        self._stop_run_button.setText("Stop run")
        self._stop_run_button.setMinimumHeight(170)
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
        self._run_plan_widget.setRunPlan(run.plan)
        self._outcome_widget.setLogHtml(run.log)
        self._outcome_widget.setElecRef(run.elec_ref)
        self._run_status_widget.setStatusMap(run.status)

    def _plan_and_start_run(self) -> None:
        run_plan = self._get_run_plan()
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
                    self._reset_device, run_plan, progress_send_stream, run_cancel_scope
                )
                run_tg.start_soon(self._monitor_run_progress, progress_receive_stream)
        # Save run
        run = Run(
            plan=run_plan,
            log=self._outcome_widget.getLogHtml(),
            elec_ref=self._outcome_widget.getElecRef(),
            status=self._run_status_widget.statusMap(),
        )
        run.to_dir(_STORAGE_DIR)
        # Refresh run history
        self._history_widget.refresh()

    async def _reset_device(
        self,
        run_plan: RunPlan,
        progress_send_stream: StatusStream,
        cancel_scope: anyio.CancelScope,
    ) -> None:
        async with progress_send_stream:
            with cancel_scope:
                try:
                    # Early out if already cancelled.
                    # TODO: Check if anyio fixed this issue upstream:
                    #
                    #     https://github.com/agronholm/anyio/issues/433
                    #
                    if cancel_scope.cancel_called:
                        raise anyio.get_cancelled_exc_class()()

                    reset_params = run_plan.parameters.reset_params
                    reset_device_settings = run_plan.steps.reset_device_settings

                    # Progress manager
                    status_map: StatusMap = {
                        **RESET_DEVICE_STATUS_MAP,
                        **SET_ELECTRONICS_REFERENCE_STATUS_MAP,
                    }

                    progress_manager = ProgressManager(
                        status_map, status_stream=progress_send_stream
                    )

                    # Device and it's description
                    device = Device.from_description(
                        reset_params.device_description, logger=_LOGGER
                    )
                    async with device:
                        await reset_device(
                            device,
                            reset_params.swu_file,
                            reset_params.branding,
                            settings=reset_device_settings,
                            progress_manager=progress_manager,
                            logger=_LOGGER,
                        )
                        if run_plan.steps.set_electronics_reference:
                            source_data = await set_electronics_reference(
                                device,
                                progress_manager=progress_manager,
                                logger=_LOGGER,
                            )
                            elec_ref = ElecRef(source_data=source_data)
                            elec_ref = await elec_ref.generate_image(
                                device_type=run_plan.parameters.device_type
                            )
                            self._outcome_widget.setElecRef(elec_ref)
                except anyio.get_cancelled_exc_class():
                    message = "User cancelled"
                    background = "grey"
                # Catch broad `Exception` as we want to handle all the general errors
                except (  # pylint: disable=broad-except
                    anyio.ExceptionGroup,
                    Exception,
                ):
                    message = format_exc()
                    background = "red"
                else:
                    message = "Done"
                    background = "green"
        style = f"color: white; background-color: {background};"
        # We add line breaks to make the message stand out
        message_html = escape_html(message)
        html = f'<pre style="{style}">{message_html}</pre>'
        self._outcome_widget.appendLogHtml(html)

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

    def _get_run_plan(self) -> Optional[RunPlan]:
        dialog = StartRunDialog(self)
        # Try get all `last_` plan from the run history
        last_partial_run = self._history_widget.latestRun()
        if last_partial_run is not None:
            try:
                last_run = Run.from_partial_run(last_partial_run)
                # Always "check" all the step fields
                last_run = last_run.with_default_steps()
                # Increment hostname if the run completed (no cancellation or errors).
                if last_run.status.overall is OverallStatus.COMPLETED:
                    last_run = last_run.with_next_hostname()
                dialog.setRunPlan(last_run.plan)
            # `ValueError`: If we can't construct `Run`
            except ValueError:
                pass
        if not dialog.exec():
            # Early out on cancel
            return None
        try:
            return dialog.model()
        # When we construct the model, we do checks such as "does this file
        # exist on the file system?". This is an invitation for race conditions.
        # Therefore, we wrap the `dialog.model()` call in a `try..catch` block.
        except ValueError as exc:
            _LOGGER.error(f"Did not start run due to invalid model: {exc}")
            _LOGGER.debug("Reason:", exc_info=exc)
            # Early out if the model is invalid
            return None

    async def _monitor_run_progress(
        self, progress_receive_stream: MemoryObjectReceiveStream[StatusMap]
    ) -> None:
        status_map: StatusMap = {}
        progress_tg = anyio.create_task_group()

        async def _receive_status() -> None:
            nonlocal status_map
            async with progress_receive_stream:
                async for status_map in progress_receive_stream:
                    run_status_map = RunStatus.from_progress_status_map(status_map)
                    self._run_status_widget.setStatusMap(run_status_map)
            progress_tg.cancel_scope.cancel()

        async def _update_status() -> None:
            while True:
                run_status_map = RunStatus.from_progress_status_map(status_map)
                self._run_status_widget.setStatusMap(run_status_map)
                await anyio.sleep(1)

        async with progress_tg:
            progress_tg.start_soon(_receive_status)
            progress_tg.start_soon(_update_status)
