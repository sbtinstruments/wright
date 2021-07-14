from __future__ import annotations

import csv
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import TracebackType
from typing import ContextManager, Optional, Type


class CommandStatus(Enum):
    """Status of a command run."""

    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(frozen=True)
class CommandLogRow:
    """Entry in the flow cell log."""

    name: str
    status: CommandStatus
    hostname: str


class CommandLog(ContextManager["CommandLog"]):
    """Log of commands used across devices."""

    def __init__(self, log_file: Path) -> None:
        self._log_file = log_file
        self._rows: list[CommandLogRow] = []

    @property
    def rows(self) -> tuple[CommandLogRow, ...]:
        """Return a copy of all rows in this log."""
        return tuple(self._rows)

    def contains(self, *, status: CommandStatus, hostname: str) -> bool:
        """Does this log contain the given hostname and status."""
        return any(
            row.hostname == hostname and row.status is status for row in self._rows
        )

    def add(self, *, status: CommandStatus, hostname: str) -> None:
        """Add row with the given fields."""
        self.add_row(CommandLogRow("reset_device", status, hostname))

    def add_row(self, row: CommandLogRow) -> None:
        """Add a complete row entry."""
        self._rows.append(row)
        self._serialize()

    def _serialize(self) -> None:
        with self._log_file.open("w", newline="") as io:
            writer = csv.writer(io)
            for row in self._rows:
                writer.writerow(("reset_device", row.status.name, row.hostname))

    def _deserialize(self) -> None:
        with self._log_file.open() as io:
            reader = csv.reader(io)
            for raw_row in reader:
                name = raw_row[0]
                status = CommandStatus[raw_row[1]]
                hostname = raw_row[2]
                row = CommandLogRow(name, status, hostname)
                self._rows.append(row)

    def __enter__(self) -> CommandLog:
        # Try to deserialize
        with suppress(OSError):
            self._deserialize()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._serialize()
