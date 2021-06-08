from functools import wraps
from logging import Logger
from typing import Any, Callable, Coroutine, Optional, TypeVar

import anyio

from ..device import DeviceDescription
from ..device.green_mango import GreenMango

ReturnType = TypeVar("ReturnType")


def with_device(
    coro: Callable[..., Coroutine[Any, Any, ReturnType]],
    *,
    device_description: DeviceDescription,
    logger: Logger,
) -> Callable[..., Coroutine[Any, Any, ReturnType]]:
    """Return coroutine function that gets a new `Device` instance on each call."""

    @wraps(coro)
    async def _with_device(*args: Any) -> ReturnType:
        # Create a new device instance for eacy run. This way, we make
        # sure that each run starts from a blank slate.
        device = GreenMango.from_description(device_description, logger=logger)
        async with device:
            return await coro(device, *args)

    return _with_device
