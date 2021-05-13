from typing import Any, Callable, Coroutine

Recipe = Callable[..., Coroutine[Any, Any, None]]

# Replace with the following callback protocol when Mypy learns how to
# check `*args: Any` properly.

# class Recipe(Protocol):  # pylint: disable=too-few-public-methods
#     """A series of steps that we run on the given device."""
#
#     async def __call__(self, __device: GreenMango, *args: Any) -> None:  # noqa: D102
#         ...
