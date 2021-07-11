from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, Extra

Derived = TypeVar("Derived", bound=BaseModel)


class FrozenModel(BaseModel):
    """Immutable model."""

    # TODO: Add root validator that ensure that all members are frozen as well

    def update(self: Derived, **kwargs: Any) -> Derived:
        """Return copy of this model updated with the given values.

        Unlike `BaseModel.copy`, this function validates the result.
        """
        items: dict[str, Any] = dict(iter(self), **kwargs)  # type: ignore[arg-type]
        return type(self)(**items)

    class Config:  # pylint: disable=too-few-public-methods
        frozen = True
        extra = Extra.forbid
