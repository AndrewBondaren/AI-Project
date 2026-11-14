"""Private configuration shared by Source records, without IO or admission."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.validation.immutableValue import validate_immutable


class SourceValue(BaseModel, frozen=True):
    model_config = ConfigDict(
        frozen=True, strict=True, extra="forbid", revalidate_instances="always",
    )

    @model_validator(mode="after")
    def immutable_value(self) -> Self:
        validate_immutable(self)
        return self
