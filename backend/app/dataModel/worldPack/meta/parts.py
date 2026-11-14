"""Absolute provenance and artifact identity at one logical Pack address."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.preparation.addresses import PackPartAddress
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance


class PackStoredPart(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    address: PackPartAddress
    artifact: ArtifactRef
    provenance: PackStoredProvenance
