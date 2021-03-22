from __future__ import annotations

import asyncio
from asyncio.streams import StreamReader, StreamWriter
from typing import Callable, Optional, Type
from types import TracebackType
import logging

_LOGGER = logging.getLogger(__name__)


_SEPARATOR = b'\x1a'

class Client:
    """TCL client for OpenOCD.
    
    See the following for reference:
    http://openocd.org/doc/html/Tcl-Scripting-API.html
    """

    def __init__(
        self,
        host: Optional[str] = None,
        *,
        output_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        if host is None:
            host = "localhost"
        self._host = host
        self._port = 6666
        self._output_cb: Optional[Callable[[str], None]] = output_cb
        self._reader: Optional[StreamReader] = None
        self._writer: Optional[StreamWriter] = None

    async def cmd(self, cmd: str) -> None:
        # Send request
        self._writer.write(cmd.encode() + _SEPARATOR)
        await self._writer.drain()
        # Wait for response
        line = await self._reader.readuntil(_SEPARATOR)
        # Remove the separator
        line = line[:-len(_SEPARATOR)]
        try:
            output = line.decode()
        except UnicodeDecodeError:
            _LOGGER.warning(f"Could not decode: {line}")
            return
        if self._output_cb is not None:
            self._output_cb(output)

    async def __aenter__(self) -> Client:
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
