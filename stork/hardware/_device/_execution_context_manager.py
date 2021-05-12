from __future__ import annotations

from logging import Logger
from types import TracebackType
from typing import TYPE_CHECKING, AsyncContextManager, Optional, Type, TypeVar, cast

from anyio.abc import AsyncResource, TaskGroup
from anyio.lowlevel import checkpoint

from . import execution_context
from ._solo_context import SoloContext

if TYPE_CHECKING:
    from ._green_mango import GreenMango

ExecutionContextT = TypeVar("ExecutionContextT", bound=execution_context.Any)


class ExecutionContextManager(AsyncResource):
    """USe to switch between execution contexts."""

    def __init__(self, device: "GreenMango", tg: TaskGroup, *, logger: Logger) -> None:
        self._device = device
        self._tg = tg
        self._logger = logger
        self._context = SoloContext()

    async def enter_context(
        self, context_type: Type[ExecutionContextT]
    ) -> ExecutionContextT:
        """Return an (entered) context of the given type.

        Returns the current context if it matches the given type.
        """
        # We intentionally use a direct type check and not `isinstance`.
        # This is because we don't want to match with subclasses
        # of the given type. E.g., so that we don't accidentally return `Linux`
        # when the user requests `QuietLinux` (even though the latter is a subclass
        # of the former).
        current_context = self._context.context
        early_out = (
            type(current_context)  # pylint:disable=unidiomatic-typecheck
            is context_type
        )
        if early_out:
            self._logger.info(
                "Already in %s. Return existing context manager.",
                context_type.__name__,
            )
            await checkpoint()
            # Early out if already in a context of the requested type
            return cast(ExecutionContextT, current_context)
        # Create the context instance
        try:
            context = context_type(self._device, self._tg)
        except Exception as exc:
            raise RuntimeError(f"Could not enter {context_type.__name__}") from exc
        # Enter the context
        return await self._context.enter_context(
            cast(AsyncContextManager[ExecutionContextT], context)
        )

    async def aclose(self) -> None:
        """Close the current context (if any)."""
        await self._context.aclose()

    async def __aenter__(self) -> ExecutionContextManager:
        await self._context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self._context.__aexit__(exc_type, exc_value, traceback)
