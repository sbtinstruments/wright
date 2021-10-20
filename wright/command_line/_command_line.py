from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, AsyncContextManager, Type, TypeVar

from pydantic import parse_raw_as

_LOGGER = logging.getLogger(__name__)

ParseType = TypeVar("ParseType")


class CommandLine(AsyncContextManager["CommandLine"]):
    """Abstract base class for a command line."""

    @abstractmethod
    async def run(self, command: str, **kwargs: Any) -> str:
        """Run command and wait for the response."""

    async def run_parsed(
        self, command: str, parse_as: Type[ParseType], **kwargs: Any
    ) -> ParseType:
        """Run command and wait for the parsed response."""
        response = await self.run(command, **kwargs)
        return parse_raw_as(parse_as, response)
