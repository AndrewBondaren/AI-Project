"""Source-local value invariants shared by POJO and request diagnostics."""

from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef


def duplicate_capture_positions(uses: tuple[SourceCaptureUsage, ...]) -> tuple[int, ...]:
    seen: set[SourceCaptureRef] = set()
    duplicates: list[int] = []
    for index, use in enumerate(uses):
        if use.capture in seen:
            duplicates.append(index)
        seen.add(use.capture)
    return tuple(duplicates)


def has_dependencies(dependencies: SourceDependencySet) -> bool:
    return bool(dependencies.objects or dependencies.collections)


def has_unique_object_identities(refs: tuple[SourceVersionRef, ...]) -> bool:
    return len({ref.object_id for ref in refs}) == len(refs)


def has_unique_collection_identities(refs: tuple[SourceCollectionVersionRef, ...]) -> bool:
    return len({ref.collection_id for ref in refs}) == len(refs)


def invalid_selection_order_positions(indices: tuple[int, ...]) -> tuple[int, ...]:
    """Inputs are structurally validated non-negative integers, in original order."""
    seen: set[int] = set()
    previous: int | None = None
    invalid: list[int] = []
    for position, index in enumerate(indices):
        if index in seen or (previous is not None and index <= previous):
            invalid.append(position)
        seen.add(index)
        previous = index
    return tuple(invalid)
