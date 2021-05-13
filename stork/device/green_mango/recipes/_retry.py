import logging
from datetime import datetime
from logging import Logger
from typing import Any, Optional

import anyio

from ..._device_description import DeviceDescription
from .._green_mango import GreenMango
from ._protocol import Recipe

_LOGGER = logging.getLogger(__name__)


async def retry(
    recipe: Recipe,
    *args: Any,
    device_description: DeviceDescription,
    logger: Logger,
    max_tries: Optional[int] = None,
) -> Any:
    """Run the given recipe and retry if it fails.

    Creates a new device instance (along with a new task group) for each run.
    """
    # Defaults
    if max_tries is None:
        max_tries = 10
    # Retry loop
    tries = 0
    while True:
        tries += 1
        completed = False
        start = datetime.now()
        # Try to run the recipe with a fresh task group and device
        try:
            # TODO: There is a bug in anyio that causes `TaskGroup` to silence
            # exceptions on CTRL+C. Therefore, we catch any exception
            # raised within the `TaskGroup` [1] and manually raise it outside [2].
            # Remove this workaround when anyio fixes the underlying issue.
            # See: https://github.com/agronholm/anyio/issues/285
            tg_exc: Optional[BaseException] = None
            async with anyio.create_task_group() as tg:
                try:
                    # Create a new device instance for eacy run. This way, we make
                    # sure that each run starts from a blank slate.
                    device = GreenMango.from_description(
                        tg, device_description, logger=logger
                    )
                    async with device:
                        result = await recipe(device, *args)
                        completed = True
                        return result
                except BaseException as exc:
                    tg_exc = exc  # [1]
                    raise
            if tg_exc is not None:
                raise tg_exc  # [2]
        # We intentionally catch all `Exception`s here so that we can retry
        # given any failure.
        except Exception as exc:  # pylint: disable=broad-except
            end = datetime.now()
            delta = end - start
            logger.info(
                'Recipe "%s" run %d out of %d failed after %d seconds with error: %s',
                recipe.__name__,
                tries,
                max_tries,
                int(delta.total_seconds()),
                f"[{type(exc).__name__}] {exc}",
            )
            logger.debug("Reason:", exc_info=exc)
            # Loop details
            if tries > max_tries:
                raise exc
        finally:
            if completed:
                end = datetime.now()
                delta = end - start
                logger.info(
                    'Recipe "%s" run %d out of %d completed after %d seconds',
                    recipe.__name__,
                    tries,
                    max_tries,
                    int(delta.total_seconds()),
                )
