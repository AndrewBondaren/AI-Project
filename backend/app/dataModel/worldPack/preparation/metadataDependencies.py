"""Transient metadata usage carried between explicit Pack operations."""

from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.worldPack.meta.metadataAttribution import (
    PackMetadataGroup, PackWildernessStatusBasis, _PackMetadataValue,
)
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject


class PackMetadataDependencyUse(_PackMetadataValue):
    group: PackMetadataGroup
    source_usage: SourceProofInput
    basis: PackWildernessStatusBasis | None


class PackMetadataDescription(_PackMetadataValue):
    subject: PackMetadataSubject
    dependencies: tuple[PackMetadataDependencyUse, ...]
