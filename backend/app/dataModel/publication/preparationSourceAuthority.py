"""Historical pinned-origin values; construction does not attest authority."""
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.artifacts.lifecycle.holders import VerifiedArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead


class PreparationSourceOriginKind(StrEnum):
    PINNED_MANIFEST = "pinned_manifest"


class PinnedManifestSourceOrigin(BaseModel, frozen=True):
    model_config = ConfigDict(strict=True, extra="forbid", revalidate_instances="always")

    kind: Literal[PreparationSourceOriginKind.PINNED_MANIFEST]
    pin: ManifestPinRead
    manifest: ArtifactRef


class PreparationSourceBinding(BaseModel, frozen=True):
    model_config = ConfigDict(strict=True, extra="forbid", revalidate_instances="always")

    target: OperationLeaseRef
    request: SourceProofReadInput
    origin: PinnedManifestSourceOrigin
    sources: tuple[VerifiedArtifactRef, ...]
