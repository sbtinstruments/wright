from datetime import timedelta
from logging import Logger, getLogger
from typing import Optional

from ..device import Device
from ..device.execution_context import DeviceLinux, enter_context
from ..device.models import ElecRef
from ..progress import Idle, ProgressManager, StatusMap
from ._power_off_on_error import power_off_on_error
from ._step import StepSettings, run_step

_LOGGER = getLogger(__name__)

SET_ELECTRONICS_REFERENCE_STATUS_MAP: StatusMap = {
    "set_electronics_reference": Idle(
        expected_duration=timedelta(seconds=150), tries=0
    ),
}


async def set_electronics_reference(
    device: Device,
    progress_manager: ProgressManager,
    *,
    settings: Optional[StepSettings] = None,
    logger: Optional[Logger] = None,
) -> Optional[ElecRef]:
    """Set electronics reference data, test it, and return said data."""
    # Defaults
    if settings is None:
        settings = StepSettings()
    if logger is None:
        logger = _LOGGER

    elec_ref = await run_step(
        power_off_on_error(_set_electronics_reference, device),
        progress_manager=progress_manager,
        settings=settings,
        logger=logger,
    )

    # Generate image (if possible)
    try:
        elec_ref = await elec_ref.generate_image()
    except Exception as exc:
        device.logger.warning("Could not generate electronics reference image")
        device.logger.debug("Reason:", exc_info=exc)

    return elec_ref


async def _set_electronics_reference(device: Device) -> ElecRef:
    async with enter_context(DeviceLinux, device) as linux:
        return await linux.set_electronics_reference()
