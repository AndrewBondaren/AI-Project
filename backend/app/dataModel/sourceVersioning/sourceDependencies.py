"""Declared dependencies. Admission, not construction, normalizes repetitions."""

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceVersionRef import (
    SourceCollectionVersionRef, SourceVersionRef,
)


class SourceDependencySet(SourceValue, frozen=True):
    objects: tuple[SourceVersionRef, ...]
    collections: tuple[SourceCollectionVersionRef, ...]
