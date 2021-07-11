from __future__ import annotations

from typing import Optional, Type

from ..model import FrozenModel
from ._device_condition import DeviceCondition
from .execution_context import Any as AnyExecutionContext


class DeviceMetadata(FrozenModel):
    """User-provided metadata for a device."""

    bundle_checksum: Optional[str] = None
    condition: DeviceCondition = DeviceCondition.UNKNOWN
    execution_context: Optional[Type[AnyExecutionContext]] = None
