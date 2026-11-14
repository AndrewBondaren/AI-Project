"""Intermediate immutable composition; completeness is checked by final admission."""

from app.dataModel.worldPack.meta.packCompositionFields import _PackCompositionFields
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataDescription
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PackPreparationState(_PackCompositionFields):
    base_publication: WorldPublicationRef
    metadata_dependencies: tuple[PackMetadataDescription, ...]
