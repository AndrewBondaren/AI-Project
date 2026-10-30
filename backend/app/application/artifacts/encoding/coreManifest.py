"""Artifact lifecycle canonical schema v1, including its shared dependency owners."""

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase, OperationClaimKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationRecord
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.holders import (
    ArtifactHolderKind, OperationHolder, ArtifactRetentionHolder, SnapshotHolder, VerifiedArtifactRef,
)
from app.dataModel.artifacts.lifecycle.gc import ArtifactStorageEventKind, GcReport
from app.dataModel.artifacts.events import ArtifactLogActivity, ArtifactLogRecord
from app.dataModel.worldSnapshot.identity.refs import SnapshotChainKind, WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef, PlayerHeadExpectation
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.apply import SnapshotCommitRefs, SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import (
    PackActivationDisposition, CasDecision, PackActivationResult, GameplayStarted,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError, ReferenceIssueContext, ReferenceIssueReason
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.spatial.facing import Facing


ARTIFACT_CORE_SCHEMA = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        # Existing shared Facing identity, used by RuntimeIssueContext.face.
        (110, Facing, CanonicalTypeKind.ENUM),
        (20001, SnapshotChainKind, CanonicalTypeKind.ENUM),
        (20002, SnapshotApplyOutcomeKind, CanonicalTypeKind.ENUM),
        (20003, ArtifactKind, CanonicalTypeKind.ENUM),
        (20004, OperationKind, CanonicalTypeKind.ENUM),
        (20005, OperationPhase, CanonicalTypeKind.ENUM),
        (20006, ArtifactHolderKind, CanonicalTypeKind.ENUM),
        (20011, PackActivationDisposition, CanonicalTypeKind.ENUM),
        (20012, CasDecision, CanonicalTypeKind.ENUM),
        (20013, OperationClaimKind, CanonicalTypeKind.ENUM),
        (20015, ArtifactLogActivity, CanonicalTypeKind.ENUM),
        (20016, ReferenceIssueReason, CanonicalTypeKind.ENUM),
        (20017, ArtifactStorageEventKind, CanonicalTypeKind.ENUM),
        (20101, WorldSnapshotRef, CanonicalTypeKind.RECORD),
        (20102, PlayerSnapshotRef, CanonicalTypeKind.RECORD),
        (20103, WorldPublicationRef, CanonicalTypeKind.RECORD),
        (20104, PlayerHeadExpectation, CanonicalTypeKind.RECORD),
        (20105, SectionStateRef, CanonicalTypeKind.RECORD),
        (20106, SectionHistoryRef, CanonicalTypeKind.RECORD),
        (20107, ArtifactRef, CanonicalTypeKind.RECORD),
        (20108, OperationLeaseRef, CanonicalTypeKind.RECORD),
        (20109, StagingReservation, CanonicalTypeKind.RECORD),
        (20110, OperationHolder, CanonicalTypeKind.RECORD),
        (20111, ArtifactRetentionHolder, CanonicalTypeKind.RECORD),
        (20112, SnapshotHolder, CanonicalTypeKind.RECORD),
        (20113, VerifiedArtifactRef, CanonicalTypeKind.RECORD),
        (20123, SnapshotCommitRefs, CanonicalTypeKind.RECORD),
        (20124, SnapshotApplyResult, CanonicalTypeKind.RECORD),
        (20125, PackActivationResult, CanonicalTypeKind.RECORD),
        (20126, GameplayStarted, CanonicalTypeKind.RECORD),
        (20127, OperationCancelled, CanonicalTypeKind.RECORD),
        (20128, OperationRecord, CanonicalTypeKind.RECORD),
        (20129, GcReport, CanonicalTypeKind.RECORD),
        (20136, ArtifactLogRecord, CanonicalTypeKind.RECORD),
        (20137, FieldPathError, CanonicalTypeKind.RECORD),
        (20138, ReferenceIssueContext, CanonicalTypeKind.RECORD),
        (20139, RuntimeIssueContext, CanonicalTypeKind.RECORD),
    )
))
