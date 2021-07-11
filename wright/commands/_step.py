from datetime import datetime
from logging import Logger
from typing import Any, Callable, Coroutine, Optional, TypeVar, overload

import anyio

from ..progress import ProgressManager
from ._settings import StepSettings

ReturnType = TypeVar("ReturnType")

# Replace `StepCoro` with the following callback protocol when Mypy learns how to
# check `*args: Any` properly.
#
# class StepCoro(Protocol):  # pylint: disable=too-few-public-methods
#     """A part of a command."""
#
#     async def __call__(self, __tg: TaskGroup, *args: Any) -> ReturnType:  # noqa: D102
StepCoro = Callable[..., Coroutine[Any, Any, ReturnType]]


# noqa
@overload
async def run_step(
    coro: StepCoro[ReturnType],
    *args: Any,
    progress_manager: ProgressManager,
    logger: Logger,
) -> ReturnType:
    """Run the step according to the given settings."""


@overload
async def run_step(
    coro: StepCoro[ReturnType],
    *args: Any,
    progress_manager: ProgressManager,
    logger: Logger,
    settings: StepSettings,
) -> Optional[ReturnType]:
    """Run the step according to the given settings."""


async def run_step(
    coro: StepCoro[ReturnType],
    *args: Any,
    progress_manager: ProgressManager,
    logger: Logger,
    settings: Optional[StepSettings] = None,
) -> Optional[ReturnType]:
    """Run the step according to the given settings."""
    # Defaults
    if settings is None:
        settings = StepSettings(True, 1)
    # Step name
    name = _get_step_name(coro)
    # Early out if disabled
    if not settings.enabled:
        await progress_manager.skip(name)
        return None
    # Run step
    return await retry(
        coro,
        *args,
        progress_manager=progress_manager,
        logger=logger,
        max_tries=settings.max_tries,
    )


async def retry(
    coro: StepCoro[ReturnType],
    *args: Any,
    progress_manager: ProgressManager,
    logger: Logger,
    max_tries: Optional[int] = None,
) -> ReturnType:
    """Run the given coroutine function and retry if it fails."""
    # Defaults
    if max_tries is None:
        max_tries = 10
    # Step name
    name = _get_step_name(coro)
    # Retry loop
    tries = 0
    while True:
        tries += 1
        completed = False
        start = datetime.now()
        # Try to run the recipe with a fresh task group and device
        try:
            async with progress_manager.step(name):
                result = await coro(*args)
                completed = True
                return result
        # We intentionally catch all `Exception`s here so that we can retry
        # given any failure.
        except (Exception, anyio.ExceptionGroup) as exc:  # pylint: disable=broad-except
            end = datetime.now()
            delta = end - start
            logger.info(
                'Recipe "%s" run %d out of %d failed after %d seconds with error: %s',
                name,
                tries,
                max_tries,
                int(delta.total_seconds()),
                f"[{type(exc).__name__}] {exc}",
            )
            logger.debug("Reason:", exc_info=exc)
            # Loop details
            if tries >= max_tries:
                raise exc
        finally:
            if completed:
                end = datetime.now()
                delta = end - start
                logger.info(
                    'Recipe "%s" run %d out of %d completed after %d seconds',
                    name,
                    tries,
                    max_tries,
                    int(delta.total_seconds()),
                )


def _get_step_name(coro: StepCoro[ReturnType]) -> str:
    return coro.__name__.strip("_")
