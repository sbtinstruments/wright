from __future__ import annotations

from typing import Optional, Type

from ..config.branding import Branding
from ..model import FrozenModel
from ..swupdate import MultiBundle
from ._device_condition import DeviceCondition
from .execution_context import Any as AnyExecutionContext


class DeviceMetadata(FrozenModel):
    """User-provided metadata for a device."""

    bundle: Optional[MultiBundle] = None
    branding: Optional[Branding] = None
    condition: DeviceCondition = DeviceCondition.UNKNOWN
    execution_context: Optional[Type[AnyExecutionContext]] = None
