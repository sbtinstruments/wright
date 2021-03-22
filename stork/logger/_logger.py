from __future__ import annotations

from typing import Dict, Optional, Type
from types import TracebackType


class OutputLogger:
    def __init__(self) -> None:
        self._buffers: Dict[str, str] = {}

    def log(self, msg: str, *, source: Optional[str] = None) -> None:
        if source is None:
            # Assume "root" source
            source = "root"
        # Get buffer for the source
        buffer = self._buffers.get(source, "")
        # Combine text from the buffer with the message
        complete_msg = buffer + msg
        # We only print new-line-separated messages. The remainder
        # goes back into the buffer
        lines = complete_msg.split("\n")
        self._buffers[source] = lines.pop()
        # Print each line (if any)
        for line in lines:
            print(f"[{source}] {line}")

    def __enter__(self) -> OutputLogger:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        """Print whatever may be in the buffers at exit."""
        for source, buffer in self._buffers.items():
            if not buffer:
                # Skip empty buffers
                continue
            print(f"[{source}] {buffer}")
