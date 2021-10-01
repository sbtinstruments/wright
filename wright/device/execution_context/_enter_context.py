from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Type, TypeVar, Union

import anyio

if TYPE_CHECKING:
    from .._device import Device
    from ._fw import DeviceUboot, Uboot, WrightLiveUboot
    from ._os import DeviceLinux, Linux, WrightLiveLinux

ExecutionContext = TypeVar(
    "ExecutionContext",
    bound=Union[
        "Uboot",
        "DeviceUboot",
        "WrightLiveUboot",
        "Linux",
        "DeviceLinux",
        "WrightLiveLinux",
    ],
)


@asynccontextmanager
async def enter_context(
    cls: Type[ExecutionContext], device: "Device", **kwargs: Any
) -> AsyncIterator[ExecutionContext]:
    """Return a context manager that enters the execution context on the device.

    This is a convenience method that creates a `TaskGroup` internally. If you
    already have a `TaskGroup`, just call the execution context's constructor directly.
    """
    async with anyio.create_task_group() as tg:
        context: ExecutionContext
        async with cls(device, tg, **kwargs) as context:  # type: ignore[call-arg]
            yield context
        tg.cancel_scope.cancel()


async def enter_and_return(
    cls: Type[ExecutionContext], device: "Device", *args: Any, **kwargs: Any
) -> None:
    """Enter the execution context and then return immediately.

    Useful if you want to prime a device. That is, if you want to boot
    a device into a given execution context (e.g., Linux) but not do
    any actual work before later.
    """
    # Early out if we are already in a context of the given type
    if cls.is_entered(device):  # type: ignore[attr-defined]
        return
    # Enter the context and do nothing
    async with enter_context(cls, device, *args, **kwargs):
        pass
