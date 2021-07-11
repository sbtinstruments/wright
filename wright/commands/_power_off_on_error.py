from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar

import anyio

from ..device import Device

ReturnType = TypeVar("ReturnType")


def power_off_on_error(
    coro: Callable[..., Coroutine[Any, Any, ReturnType]],
    device: Device,
) -> Callable[..., Coroutine[Any, Any, ReturnType]]:
    """Return coroutine function that powers off the device on error."""

    @wraps(coro)
    async def _power_off_on_error(*args: Any) -> ReturnType:
        try:
            return await coro(device, *args)
        except (Exception, anyio.ExceptionGroup) as exc:
            await device.hard_power_off()
            raise exc

    return _power_off_on_error
