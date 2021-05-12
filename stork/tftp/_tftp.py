from __future__ import annotations

import asyncio
import logging
from asyncio.protocols import BaseProtocol
from asyncio.transports import BaseTransport
from pathlib import Path
from types import TracebackType
from typing import Optional, Type, cast

from ._protocol import TFTPServerProtocol

_LOGGER = logging.getLogger(__name__)


class AsyncTFTPServer:
    """TFTP server.

    Serves files from the current working directory.
    """

    def __init__(self, host: str, port: int, *, directory: Path) -> None:
        self._host = host
        self._port = port
        self._directory = directory
        self._transport: Optional[BaseTransport] = None
        self._protocol: Optional[BaseProtocol] = None

    async def __aenter__(self) -> AsyncTFTPServer:
        loop = asyncio.get_event_loop()

        def _protocol_factory() -> BaseProtocol:
            protocol = TFTPServerProtocol(
                self._host, loop, directory=self._directory, extra_opts=None
            )
            return cast(BaseProtocol, protocol)

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            _protocol_factory, local_addr=(self._host, self._port)
        )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        _LOGGER.info("Stop TFTP server...")
        if self._transport is not None:
            self._transport.close()
