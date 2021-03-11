from typing import Any, AsyncGenerator
from ._step import Step


StepByStepCommand = AsyncGenerator[Step, Any]
