from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class Instruction:
    text: Optional[str] = None


@dataclass(frozen=True)
class RequestConfirmation:
    text: Optional[str] = None


StatusUpdate = str

Step = Union[StatusUpdate, Instruction, RequestConfirmation]
