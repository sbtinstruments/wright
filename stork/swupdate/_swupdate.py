from pathlib import Path
from typing import Callable, Optional

from ..subprocess import Subprocess

_CPIO_EXE = "cpio"


async def extract_swu(
    swu: Path, *, output_cb: Optional[Callable[[str], None]] = None
) -> None:
    """Extract the SWU file contents to the current working directory."""
    with swu.open("rb", 0) as f:
        args = ["-idv"]
        await Subprocess.run(_CPIO_EXE, *args, stdin=f, output_cb=output_cb)
