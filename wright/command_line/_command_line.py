from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, AsyncContextManager, Optional

_LOGGER = logging.getLogger(__name__)


class CommandLine(AsyncContextManager["CommandLine"]):
    """Abstract base class for a command line."""

    @abstractmethod
    async def cmd(self, cmd: str, **kwargs: Any) -> Optional[str]:
        """Execute the given command on the device."""
