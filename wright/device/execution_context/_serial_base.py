from abc import abstractmethod
from contextlib import AsyncExitStack
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Optional,
    Type,
    TypeVar,
    cast,
)

from anyio.abc import TaskGroup

from ...command_line import SerialCommandLine
from ._base import Base

if TYPE_CHECKING:
    from .._device import Device

Derived = TypeVar("Derived", bound="Base")


class SerialBase(Base):
    """Execution context that sends commands over a command line."""

    def __init__(self, device: "Device", tg: TaskGroup) -> None:
        super().__init__(device, tg)
        self._serial: Optional[SerialCommandLine] = None
        self._stack: Optional[AsyncExitStack] = None

    @property
    def serial(self) -> SerialCommandLine:
        """Return the serial command line."""
        self._raise_if_not_entered()
        self._raise_if_exited()
        assert self._serial is not None
        return self._serial

    @abstractmethod
    def _serial_cm(self) -> AsyncContextManager[SerialCommandLine]:
        ...

    def _create_serial(self, prompt: str) -> SerialCommandLine:
        """Create an (unentered) serial command line.

        This is a helper method that sets up some defaults for, e.g.,
        logging.
        """
        # Logger
        if self._logger is None:
            serial_logger = None
        else:
            serial_logger = self._logger.getChild("serial")
        # Command line
        return SerialCommandLine(
            self._tg,
            self._dev.link.communication.tty,
            prompt,
            logger=serial_logger,
        )

    async def cmd(self, *args: Any, **kwargs: Any) -> Optional[str]:
        """Send command through the command line."""
        return await self.serial.cmd(*args, **kwargs)

    async def aclose(self) -> None:
        """Close this context.

        Use this if you issued a command that invalidates this execution context.
        E.g., if you boot into Linux from U-boot.
        """
        self._raise_if_not_entered()
        self._raise_if_exited()
        assert self._stack is not None
        await self._stack.aclose()
        self._dev.metadata = self._dev.metadata.update(execution_context=None)

    async def __aenter__(self) -> Derived:
        await self._boot_if_necessary()
        async with AsyncExitStack() as stack:
            # Listen over serial. E.g., to get the boot log.
            self._serial = await stack.enter_async_context(self._serial_cm())
            # Mark this context as "entered"
            await super().__aenter__()
            # Transfer ownership to this instance
            self._stack = stack.pop_all()
        return cast(Derived, self)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        assert self._stack is not None
        try:
            await self._stack.__aexit__(exc_type, exc_value, traceback)
        finally:
            await super().__aexit__(exc_type, exc_value, traceback)
