"""Exact live revision-to-artifact mappings; no body access or hash computation."""

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef


class SourceBodyVersion(SourceValue, frozen=True):
    source: SourceVersionRef
    body: ArtifactRef


class SourceCollectionVersion(SourceValue, frozen=True):
    source: SourceCollectionVersionRef
    body: ArtifactRef
