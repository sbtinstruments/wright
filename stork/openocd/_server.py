from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from ..subprocess import Subprocess

_OPENOCD_EXE = os.environ.get("STORK_OPENOCD_EXE", "openocd")


class Server(Subprocess):
    def __init__(
        self,
        cfg_file: str,
        output_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        debug = False
        args = ["-f", cfg_file]
        if debug:
            args.append("-d3")
        super().__init__(
            _OPENOCD_EXE,
            *args,
            raise_on_rc=False,
            terminate_on_exit=True,
            output_cb=output_cb
        )
