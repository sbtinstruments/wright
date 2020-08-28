from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass
import socket
import subprocess


@dataclass(frozen=True)
class FilePart:
    """Part of a larger file identified by an offset into said file."""

    path: Path
    offset: int


def split_file(file: Path, *, chunk_size: Optional[int] = None) -> List[FilePart]:
    """Split file into parts while skipping null-bytes.

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
    with file.open("rb") as f:
        done = False
        while not done:
            part_data = bytes()
            offset = f.tell()
            # Read until we reach the sentinel or there is no more data
            while chunk := f.read(chunk_size):
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
            part_path = Path(f"part_offset{offset}.bin")
            with part_path.open("wb") as part_file:
                part_file.write(part_data)
            result.append(FilePart(part_path, offset))
    return result


def extract_swu(swu: Path) -> None:
    """Extract the SWU file contents to the current working directory."""
    with swu.open("rb", 0) as f:
        subprocess.run(["cpio", "-idv"], stdin=f, check=True)


def get_local_ip():
    """Return the local IP address of this machine.

    Inspiration: https://stackoverflow.com/a/166589/554283
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    try:
        return s.getsockname()[0]
    finally:
        s.close()
