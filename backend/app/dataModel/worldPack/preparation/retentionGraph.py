"""Inputs and policy for internal Pack retention admission; no completion evidence."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid


class PackRetentionCollectInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    manifest: ArtifactRef
    world_uid: EntityUid


class PackRetentionBudget(BaseModel):
    """Per-collect descriptor-byte reservations and distinct artifact count."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    max_read_bytes: Annotated[StrictInt, Field(gt=0)]
    max_artifacts: Annotated[StrictInt, Field(gt=0)]
