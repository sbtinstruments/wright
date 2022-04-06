from __future__ import annotations

from logging import Logger, getLogger
from types import TracebackType
from typing import Any, Optional, Type

import asyncssh
from asyncssh import (
    ProcessError,
    SSHClientConnection,
    SSHCompletedProcess,
    SSHKnownHosts,
)

_LOGGER = getLogger(__name__)

from ._command_line import CommandLine


class SshCommandLine(CommandLine):
    """SSH-based command line used to send commands to the device."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        host_key: str,
        username: str,
        logger: Optional[Logger] = None,
    ) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._host_key = host_key
        self._username = username
        if logger is None:
            logger = _LOGGER
        self._logger = logger
        self._conn: Optional[SSHClientConnection] = None

    async def run(self, command: str, **kwargs: Any) -> str:
        """Run command and wait for the response."""
        if self._conn is None:
            raise RuntimeError("Call __aenter__ before you issue a command")
        try:
            process: SSHCompletedProcess = await self._conn.run(command, check=True)
        except ProcessError as exc:
            self._logger.debug(f"stdout:\n{exc.stdout}")
            self._logger.debug(f"stderr:\n{exc.stderr}")
            raise
        response = process.stdout
        assert isinstance(response, str)
        return response

    @property
    def _known_hosts(self) -> SSHKnownHosts:
        data = f"{self._host} {self._host_key}\n"
        return SSHKnownHosts(data)

    async def __aenter__(self) -> SshCommandLine:
        conn = asyncssh.connect(
            self._host,
            self._port,
            known_hosts=self._known_hosts,
            username=self._username,
        )
        self._conn = await conn.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        assert self._conn is not None
        await self._conn.__aexit__(exc_type, exc_value, traceback)
