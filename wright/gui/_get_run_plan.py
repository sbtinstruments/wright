import logging
from pathlib import Path
from typing import Optional

from ..device import DeviceType
from ..device.models import Branding
from .models import OverallStatus, Run, RunPlan, RunParameters, RunSteps
from .widgets._history_widget import HistoryWidget
from .widgets._start_run_dialog import StartRunDialog
from PyQt5.QtWidgets import QWidget
from .globals import SHIPYARD_DIR

_LOGGER = logging.getLogger()  # root logger


def get_run_plan(parent: QWidget, history_widget: HistoryWidget) -> Optional[RunPlan]:
    dialog = StartRunDialog(parent)
    plan: Optional[RunPlan] = None
    # Try get all `last_` plan from the run history
    last_partial_run = history_widget.latestRun()
    if last_partial_run is not None:
        try:
            last_run = Run.from_partial_run(last_partial_run)
            # Always "check" all the step fields
            last_run = last_run.with_default_steps()
            # Increment hostname if the run completed (no cancellation or errors).
            if last_run.base.status.overall is OverallStatus.COMPLETED:
                last_run = last_run.with_next_pcb_id()
            plan = last_run.base.plan
        # `ValueError`: If we can't construct `Run`
        except ValueError as exc:
            _LOGGER.warning(f"Could not reconstruct last run: {exc}")
            _LOGGER.debug("Reason:", exc_info=exc)
    # Default plan for the dialog
    if plan is None:
        parameters = RunParameters(
            device_type=DeviceType.BACTOBOX,
            pcb_identification_number="XXXXXYYWW000",
            device_version="",
            hostname="bbYYWW000",
            swu_file=_get_default_swu_file(),
            branding=Branding.SBT,
        )
        plan = RunPlan(parameters=parameters, steps=RunSteps())
    dialog.setRunPlan(plan)

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


def _get_default_swu_file() -> Path:
    # Return the first SWU file in the shipyard directory
    swu_files = (item for item in SHIPYARD_DIR.glob("*.swu") if item.is_file())
    for swu_file in swu_files:
        return swu_file
    return Path()
