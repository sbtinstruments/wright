from datetime import timedelta
from logging import Logger, getLogger
from typing import Optional

from ..device import Device
from ..device.execution_context import DeviceLinux, enter_context
from ..device.models import FrequencySweep
from ..progress import Idle, ProgressManager, StatusMap

_LOGGER = getLogger(__name__)

SET_ELECTRONICS_REFERENCE_STATUS_MAP: StatusMap = {
    "set_electronics_reference": Idle(
        expected_duration=timedelta(seconds=150), tries=0
    ),
}


async def set_electronics_reference(
    device: Device,
    progress_manager: ProgressManager,
    logger: Optional[Logger] = None,
) -> FrequencySweep:
    """Set electronics reference data and return said data."""
    # Defaults
    if logger is None:
        logger = _LOGGER

    async with progress_manager.step("set_electronics_reference"):
        async with enter_context(DeviceLinux, device) as linux:
            return await linux.set_electronics_reference()
