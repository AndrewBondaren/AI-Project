"""Patch core schema v1: declarations only; no concrete domain section IDs."""

from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.patch.changes.header import PatchRef, PatchHeader
from app.dataModel.patch.sections.dependency import SectionDependencyKind, PreparedSectionDependency, PublishedSectionDependency
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.patch.preconditions.runtime import (
    RuntimeVersionKind, TargetExpectationKind, TargetPresence, PackTargetVersion, SnapshotTargetVersion,
    TargetAbsent, TargetVersionExpected,
)
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionRefused, SectionApplyReceipt


PATCH_CORE_SCHEMA = CanonicalSchemaManifest(entries=ARTIFACT_CORE_SCHEMA.entries + tuple(
    RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        (20007, SectionDependencyKind, CanonicalTypeKind.ENUM),
        (20008, RuntimeVersionKind, CanonicalTypeKind.ENUM),
        (20009, TargetExpectationKind, CanonicalTypeKind.ENUM),
        (20010, TargetPresence, CanonicalTypeKind.ENUM),
        (20114, PatchRef, CanonicalTypeKind.RECORD),
        (20115, PatchHeader, CanonicalTypeKind.RECORD),
        (20116, PreparedSectionDependency, CanonicalTypeKind.RECORD),
        (20117, PublishedSectionDependency, CanonicalTypeKind.RECORD),
        (20118, SectionHeader, CanonicalTypeKind.RECORD),
        (20119, PackTargetVersion, CanonicalTypeKind.RECORD),
        (20120, SnapshotTargetVersion, CanonicalTypeKind.RECORD),
        (20121, TargetAbsent, CanonicalTypeKind.RECORD),
        (20122, TargetVersionExpected, CanonicalTypeKind.RECORD),
        (20130, SectionAccepted, CanonicalTypeKind.RECORD),
        (20131, SectionRefused, CanonicalTypeKind.RECORD),
        (20132, SectionApplyReceipt, CanonicalTypeKind.RECORD),
    )
))
