"""Position of a validated POJO inside an import document (F09, not a field path).

Plan: ``.cursor/plans/error-contracts-1.md`` jsonValidation D1. ``()`` is the
document root; parts are wire keys, uids and indexes.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

type WirePart = StrictStr | Annotated[StrictInt, Field(ge=0)]


class WireLocation(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    parts: tuple[WirePart, ...] = ()

    def child(self, *parts: str | int) -> Self:
        return type(self)(parts=(*self.parts, *parts))
