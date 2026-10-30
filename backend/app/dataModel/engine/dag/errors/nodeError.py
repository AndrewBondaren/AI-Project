"""Base for declared operation errors; no execution policy or exceptions."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.validation.immutableValue import validate_immutable


class NodeError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    @model_validator(mode="after")
    def check_immutable_error(self) -> Self:
        validate_immutable(self)
        return self
