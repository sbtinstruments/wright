from typing import Any, AsyncGenerator, Union
from . import steps

Step = Union[steps.StatusUpdate, steps.Instruction, steps.RequestConfirmation]

StepByStepCommand = AsyncGenerator[Step, Any]
