import asyncio
import logging
from asyncio.protocols import Protocol
from asyncio.transports import Transport
from types import TracebackType
from typing import Optional, Type

from py3tftp.protocols import TFTPServerProtocol

_LOGGER = logging.getLogger(__name__)


class AsyncTFTPServer:
    """TFTP server
    
    Serves files from the current working directory.
    """

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._transport: Optional[Transport] = None
        self._protocol: Optional[Protocol] = None

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: TFTPServerProtocol(self._host, loop, extra_opts=None),
            local_addr=(
                self._host,
                self._port,
            ),
        )
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType,
    ) -> None:
        _LOGGER.info("Stopping TFTP server...")
        self._transport.close()
