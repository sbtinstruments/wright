# HACK: The following is a hack to py3tftp so that it can serve files
# from other directories than the CWD.
#
# py3tftp is not typed. Therefore, we ignore a lot of type-related
# errors here and use `Any` a lot.
#
# pylint: disable-all

import os
from pathlib import Path
from typing import Any

from py3tftp.file_io import FileReader, FileWriter  # type: ignore
from py3tftp.netascii import Netascii  # type: ignore
from py3tftp.protocols import TFTPServerProtocol  # type: ignore


def patch_py3tftp() -> None:
    """Monkeypatch various classes from py3tftp."""
    _original__init__ = TFTPServerProtocol.__init__

    def _patched__init__(self: Any, *args: Any, directory: Path, **kwargs: Any) -> None:
        _original__init__(self, *args, **kwargs)
        self._directory = directory

    def _patched_select_file_handler(self: Any, packet: Any) -> Any:
        """Return the file handler that corresponds to the packet."""
        if packet.is_wrq():
            return lambda filename, opts: FileWriter(
                filename, self._directory, opts, packet.mode
            )
        else:
            return lambda filename, opts: FileReader(
                filename, self._directory, opts, packet.mode
            )

    TFTPServerProtocol.__init__ = _patched__init__
    TFTPServerProtocol.select_file_handler = _patched_select_file_handler

    def _file_reader__init__(
        self: Any, fname: Any, directory: Path, chunk_size: int = 0, mode: Any = None
    ) -> None:
        self._f = None
        self.fname = _sanitize_fname(fname, directory)
        self.chunk_size = chunk_size
        self._f = self._open_file()
        self.finished = False

        if mode == b"netascii":
            self._f = Netascii(self._f)

    FileReader.__init__ = _file_reader__init__

    def _file_writer__init__(
        self: Any, fname: Any, directory: Path, chunk_size: int, mode: Any = None
    ) -> None:
        self._f = None
        self.fname = _sanitize_fname(fname, directory)
        self.chunk_size = chunk_size
        self._f = self._open_file()

        if mode == b"netascii":
            self._f = Netascii(self._f)

    FileWriter.__init__ = _file_writer__init__

    def _sanitize_fname(fname: bytes, directory: Path) -> Path:
        path = (directory / os.fsdecode(fname)).absolute()
        # Verify that the path is within the directory
        if not path.is_relative_to(directory):
            raise FileNotFoundError
        # Verify that the path is not reserved
        if path.is_reserved():
            raise FileNotFoundError
        return path


# Apply the patch on import
patch_py3tftp()
