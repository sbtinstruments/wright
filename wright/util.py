from __future__ import annotations

import socket
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, List, Optional, Type

TEMP_DIR = Path("/tmp/wright")


@dataclass(frozen=True)
class FilePart:
    """Part of a larger file identified by an offset into said file."""

    path: Path
    offset: int


def split_file(file_path: Path, *, chunk_size: Optional[int] = None) -> List[FilePart]:
    r"""Split file into parts while skipping null-bytes.

    Imagine that the following byte sequence represents a large file:

        10110111100100000000000000000010101000000000101110

    First, we split it into chunks:

        | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
        10110111100100000000000000000010101000000000101110

    Then, we output the non-null chunks into separate files:

        | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
        10110111100100000000000000000010101000000000101110
        \_____________/               \___/     \________/
            Part 0                    Part 1      Part 2

        Part 0: C0–C2 goes into "part_offset0.bin"
        Part 1:    C6 goes into "part_offset30.bin"
        Part 2: C8–C9 goes into "part_offset40.bin"

    This way, we effectively skip most of the null-bytes.
    """
    result = []
    # Default arguments
    if chunk_size is None:
        chunk_size = 1024 * 1024  # 1 MiB
    # The sentinel is a series of null bytes. When we reach the
    # sentinel while reading the file, we start skipping.
    sentinel = bytes(chunk_size)
    with file_path.open("rb") as io:
        done = False
        while not done:
            part_data = bytes()
            offset = io.tell()
            # Read until we reach the sentinel or there is no more data
            while chunk := io.read(chunk_size):
                if chunk == sentinel:
                    break
                part_data += chunk
            else:
                done = True
            # If there is no data to write out (it was all null bytes),
            # we early out.
            if not part_data:
                continue
            # Otherwise, we write the data out to as a file.
            part_path = TEMP_DIR / f"{file_path.name}__offset_{offset}.bin"
            with part_path.open("wb") as part_io:
                part_io.write(part_data)
            result.append(FilePart(part_path, offset))
    return result


def get_local_ip() -> Any:
    """Return the local IP address of this machine.

    Inspiration: https://stackoverflow.com/a/166589/554283
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    try:
        return sock.getsockname()[0]
    finally:
        sock.close()


def get_first_tty() -> Path:
    """Get the first available USB-connected TTY."""
    specific_ttys = (Path(f"/dev/ttyGreenMango{i}") for i in range(9))
    generic_ttys = (Path(f"/dev/ttyUSB{i}") for i in range(9))
    ttys = chain(specific_ttys, generic_ttys)
    existing_ttys = (tty for tty in ttys if tty.exists())
    try:
        return next(iter(existing_ttys))
    except StopIteration as exc:
        raise RuntimeError("Could not determine tty") from exc


class DelimitedBuffer:
    """Split a stream into delimited chunks."""

    def __init__(
        self, on_next: Callable[[str], None], *, delimiter: Optional[str] = None
    ) -> None:
        self._on_next = on_next
        self._delimiter = "\n" if delimiter is None else delimiter
        self._buffer: str = ""

    def on_next(self, text: str) -> None:
        """Push an item into the stream."""
        # Combine text from the buffer with the given text
        complete_text = self._buffer + text
        # Output the lines. The remainder goes back into the buffer
        lines = complete_text.split(self._delimiter)
        self._buffer = lines.pop()
        # Print each line (if any)
        for line in lines:
            self._on_next(line)

    def __enter__(self) -> DelimitedBuffer:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Output whatever may be in the buffer at exit."""
        if self._buffer:
            self._on_next(self._buffer)
