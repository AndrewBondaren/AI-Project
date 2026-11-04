"""Typed direct field selection shared by Cascade, policies and field paths.

Plan: ``.cursor/plans/error-contracts-1.md`` §0.1.1.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)
ValueT = TypeVar("ValueT")


@dataclass(frozen=True)
class FieldRef(Generic[ModelT, ValueT]):
    """Statically checked direct field selection, with deferred model lookup."""

    model: Callable[[], type[ModelT]]
    select: Callable[[ModelT], ValueT]
