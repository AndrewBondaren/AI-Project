"""A completed plan revision, separate from its input lookup identity."""

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.planning.identity.planKey import OutputFingerprint, PlanKey


class PlanRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: PlanKey
    output_fingerprint: OutputFingerprint = Field(strict=True, min_length=32, max_length=32)
