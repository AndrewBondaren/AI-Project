"""Distinct references to an object revision and a membership revision."""

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceObjectId import SourceCollectionId, SourceObjectId
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision


class SourceVersionRef(SourceValue, frozen=True):
    object_id: SourceObjectId
    revision: SourceRevision


class SourceCollectionVersionRef(SourceValue, frozen=True):
    collection_id: SourceCollectionId
    revision: SourceRevision
