"""Composition identity and parameters, without field evaluation."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictFloat


class FieldCompositionOperator(StrEnum):
    ADD_CLAMP = "add_clamp"


class FieldCompositionPolicy(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always", validate_default=True)

    operator: FieldCompositionOperator = FieldCompositionOperator.ADD_CLAMP
    detail_weight: StrictFloat = Field(default=0.20, ge=0, le=1, allow_inf_nan=False)
