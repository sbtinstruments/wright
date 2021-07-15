from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar, cast

from .._device_condition import DeviceCondition
from ._base import Base

T = TypeVar("T", bound=Callable[..., Coroutine[Any, Any, Any]])


def deteriorate(condition: DeviceCondition) -> Callable[[T], T]:
    """Apply the given wear and tear to the device."""

    def _deteriorate(coro: T) -> T:
        @wraps(coro)
        async def _wrapper(self: Base, *args: Any, **kwargs: Any) -> Any:
            try:
                return await coro(self, *args, **kwargs)
            finally:
                new_condition = min(self.device.metadata.condition, condition)
                self.device.metadata = self.device.metadata.update(
                    condition=new_condition
                )

        return cast(T, _wrapper)

    return _deteriorate
