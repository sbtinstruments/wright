from __future__ import annotations

from contextlib import AsyncExitStack
from logging import Logger, getLogger
from types import TracebackType
from typing import Optional, Type

import anyio
from anyio.abc import SocketStream

from ..util import DelimitedBuffer

_LOGGER = getLogger(__name__)


_SEPARATOR = b"\x1a"


class Client:
    """TCL client for OpenOCD.

    See the following for reference:
    http://openocd.org/doc/html/Tcl-Scripting-API.html
    """

    def __init__(
        self,
        host: Optional[str] = None,
        *,
        logger: Optional[Logger] = None,
    ) -> None:
        if host is None:
            host = "localhost"
        if logger is None:
            logger = _LOGGER
        self._host = host
        self._port = 6666
        self._logger: Logger = logger
        self._logger_info = DelimitedBuffer(self._logger.info)
        self._stream: Optional[SocketStream] = None
        self._stack: Optional[AsyncExitStack] = None

    async def run(self, command: str) -> None:
        """Run command on the OCD server."""
        # Early out
        if self._stream is None:
            raise RuntimeError("Enter client context first")
        # Send the request
        await self._stream.send(command.encode() + _SEPARATOR)
        # Wait for a response
        response_data = await self._stream.receive()
        # Split the raw response. If everything goes as planned, we get something
        # like the following:
        #
        #   responses[0] == b"hello world"
        #   responses[1] == b""
        #
        # Note the empty `bytes` object.
        responses = response_data.split(_SEPARATOR)
        # `split` always returns a non-empty list. Even if the separator
        # isn't found (in this case `split` returns the entire string as a
        # single-element list).
        assert len(responses) > 0
        first_response = responses.pop(0)
        # We expect a single response from the server. Anything else
        # results in a warning.
        if responses and responses[0]:
            self._logger.warning(
                "Server sent multiple responses. We use the "
                "first and discard the remaining %s responses.",
                len(responses),
            )
            for response in responses:
                self._logger.debug("Discarded response: %s", response)
        # Decode response. Warn if it fails.
        try:
            output = first_response.decode()
        except UnicodeDecodeError:
            self._logger.warning("Could not decode: %s", first_response)
            return
        self._logger_info.on_next(output)

    async def __aenter__(self) -> Client:
        async with AsyncExitStack() as stack:
            stack.enter_context(self._logger_info)
            self._stream = await anyio.connect_tcp(self._host, self._port)
            await stack.enter_async_context(self._stream)
            # Transfer ownership to this instance
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        assert self._stack is not None
        await self._stack.__aexit__(exc_type, exc_value, traceback)
