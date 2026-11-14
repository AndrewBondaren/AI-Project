"""Private configuration shared by Source records, without IO or admission."""

# TODO(SOURCE-TYPED-ERRORS): Complete the agreed SourceFieldIssue/SourceLogicIssue
# and SourceFailure diagnostic boundary, with typed codes/paths and aggregation
# of independent failures. Current Pydantic/ValueError validation does not close
# that acceptance criterion; the POJO slice remains incomplete in this respect.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

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
