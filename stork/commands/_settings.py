from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StepSettings:
    """Settings for a step in a command."""

    enabled: bool = True
    max_tries: Optional[int] = None


@dataclass(frozen=True)
class ResetDeviceSettings:
    """Settings for each (configurable) step in the reset device command."""

    reset_firmware: StepSettings = StepSettings()
    reset_software: StepSettings = StepSettings()
    reset_config: StepSettings = StepSettings()
    reset_data: StepSettings = StepSettings()
