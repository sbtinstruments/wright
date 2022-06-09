import logging
from typing import Optional

from .models import OverallStatus, Run, RunPlan
from .widgets._history_widget import HistoryWidget
from .widgets._start_run_dialog import StartRunDialog
from PyQt5.QtWidgets import QWidget

_LOGGER = logging.getLogger()  # root logger


def get_run_plan(parent: QWidget, history_widget: HistoryWidget) -> Optional[RunPlan]:
    dialog = StartRunDialog(parent)
    # Try get all `last_` plan from the run history
    last_partial_run = history_widget.latestRun()
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
        except ValueError as exc:
            _LOGGER.warning(f"Could not reconstruct last run: {exc}")
            _LOGGER.debug("Reason:", exc_info=exc)
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
