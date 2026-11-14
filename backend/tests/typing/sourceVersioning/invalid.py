"""Exactly five expected errors: refs, collection union, owner brand, tuple, frozen."""

from app.dataModel.artifacts.references import ArtifactFormatKey
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorKey
from app.dataModel.sourceVersioning.sourceObjectId import SourceCollectionId
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef


def rejected(
    obj: SourceVersionRef, collection: SourceCollectionVersionRef,
    identity: SourceCollectionId, revision: SourceRevision, foreign_key: ArtifactFormatKey,
) -> None:
    SourceDependencySet(objects=(collection,), collections=())
    SourceVersionRef(object_id=identity, revision=revision)
    key: SourceDescriptorKey = foreign_key
    SourceDependencySet(objects=[obj], collections=())
    revision.seq = 2
