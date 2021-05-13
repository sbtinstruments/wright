from __future__ import annotations

from types import TracebackType
from typing import Any, AsyncContextManager, Optional, Type, TypeVar

from anyio.abc import AsyncResource

T = TypeVar("T")


class SoloContext(AsyncResource):
    """Holds a single (entered) context manager.

    Like a `contextlib.AsyncExitStack` with only a single element.
    When you call `enter_context`, it automatically exits
    the current context (if any).

    Example:
        async with SoloContext() as solo:
            # Open file1
            file1 = solo.enter_context(open("file1.txt"))
            print(file1.read())
            # Open file2
            file2 = solo.enter_context(open("file2.txt"))
            assert file1.closed
            print(file2.read())
            # Open file3 (conditionally)
            if some_boo:
                file3 = solo.enter_context(open("file3.txt"))
                assert file2.closed
                print(file3.read())
            # Either file2 or file3 is open at this point
        assert file2.closed
        assert file3.closed

    Like with `contextlib.AsyncExitStack`, `SoloContext` becomes interesting
    when the control flow is conditional (as with `file3` in the example).
    Otherwise, you're better off with separate `with` statements.
    """

    def __init__(self) -> None:
        self._context: Optional[AsyncContextManager[Any]] = None
        # Use a sentinel for the context value since `None` is an appropriate value.
        self._context_value: Any = _Sentinel

    @property
    def context(self) -> Optional[AsyncContextManager[Any]]:
        """Return current context."""
        return self._context

    def context_value(self) -> Any:
        """Return current context value.

        This is the value returned by the current context's `__aenter__` call.

        Raises `RuntimeError` if there is no current context.
        """
        if self._context_value is _Sentinel:
            raise RuntimeError("There is no current context.")
        return self._context_value

    async def enter_context(self, context: AsyncContextManager[T]) -> T:
        """Enter the given context and return the result.

        We automatically exit the current context (if any). It's up to the caller to
        make sure that they no longer use the current context.
        """
        # Exit the current context (if any). Note that we do this *after*
        # we enter the new context. This way, `context.__aenter__` can call
        # `enter_context` internally (and, in turn, use the current context).
        #
        # If the exit fails, we propagate the exception. Note that we never
        # enter `context` in this case. It's simply garbage-collected.
        await self.aclose()
        assert self._context is None
        assert self._context_value is _Sentinel
        # Enter the context and save the returned value. Propagate the exception
        # on error.
        self._context_value = await context.__aenter__()
        # Note that we assign `_context` after the `__aenter__` call. This way,
        # we are sure that the stored context is always entered.
        self._context = context
        return self._context_value

    async def aclose(self) -> None:
        """Close the current context (if any)."""
        # Exit the context. The `None` arguments indicate that no
        # exception occurred.
        await self.__aexit__(None, None, None)

    async def __aenter__(self) -> SoloContext:
        # This class is not reentrant. The following asserts make sure of it.
        assert self._context is None
        assert self._context_value is _Sentinel
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        # Early out
        if self._context is None:
            return
        try:
            await self._context.__aexit__(exc_type, exc_value, traceback)
        finally:
            # No matter what, we clear the current context
            self._context = None
            self._context_value = _Sentinel


class _Sentinel:  # pylint: disable=too-few-public-methods
    pass
