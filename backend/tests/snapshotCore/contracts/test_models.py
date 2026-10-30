"""Core 4A1–4A3: DTO invariants, strict validation, immutability and boundaries."""

import ast
import json
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.dataModel.artifacts.references import (
    ArtifactFormatMetadata, ArtifactFormatRegistry, ArtifactKind, ArtifactRef,
)
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata, PatchSectionRegistry
from app.dataModel.patch.values import FormatVersion, PatchOrdinal
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.dependency import (
    PreparedSectionDependency, PublishedSectionDependency, SectionDependency,
)
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.preconditions.runtime import (
    PackTargetVersion, SnapshotTargetVersion, RuntimeTargetExpectation,
    TargetAbsent, TargetPresence, TargetVersionExpected,
)
from app.dataModel.patch.results.sectionResult import (
    SectionAccepted, SectionApplyReceipt, SectionRefused, SectionValidation,
)
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import (
    PlayerSnapshotRef, SnapshotChainKind, SnapshotRef, WorldSnapshotRef,
)
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


from app.dataModel.worldSnapshot.metadata.envelope import (
    CreatedAtUtc, WorldSnapshotMetadata, PlayerSnapshotMetadata, SnapshotEnvelope,
)
from app.dataModel.worldSnapshot.results.apply import SnapshotCommitRefs, SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import (
    PackActivationDisposition, PackActivationResult, GameplayStarted, CasDecision,
)
from app.dataModel.worldSnapshot.events import SnapshotLogActivity, SnapshotLogRecord
from app.dataModel.artifacts.events import ArtifactLogActivity, ArtifactLogRecord
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase, OperationClaimKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancelled
from app.dataModel.artifacts.lifecycle.operation.claim import (
    PublicationOwner, PublicationTerminal, PublicationBusy, OperationClaim,
)
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.holders import (
    OperationHolder, ArtifactRetentionHolder, SnapshotHolder, ArtifactHolderRef, VerifiedArtifactRef,
)
from app.dataModel.artifacts.lifecycle.gc import GcReport, ArtifactStorageEventKind
from app.application.worldSnapshot.logging.snapshotLog import SnapshotLifecycleLog
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.core.loggingConfig import JsonLogFormatter, request_id_var

class CoreModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldSnapshotRef(world_uid="world", timeline_id="main", snapshot_id="tick-1")
        self.player = PlayerSnapshotRef(player_uid="player", snapshot_id="tick-1")
        self.section_key = RegistryKey[PatchSectionRegistry]("regions.state")
        self.format_key = RegistryKey[ArtifactFormatRegistry]("regions.state.rows")
        self.artifact = ArtifactRef(
            kind=ArtifactKind.SQL_ROWS, format_key=self.format_key, format_version=1,
            content_hash="a" * 64, nbytes=100, row_count=2,
        )

    def test_strict_numeric_value_contracts(self) -> None:
        for annotation, good in ((FormatVersion, 1), (PatchOrdinal, 0)):
            adapter = TypeAdapter(annotation)
            self.assertEqual(adapter.validate_python(good), good)
            for bad in (True, False, -1, "1", 1.0, None):
                with self.subTest(annotation=annotation, value=bad), self.assertRaises(ValidationError):
                    adapter.validate_python(bad)
        with self.assertRaises(ValidationError):
            TypeAdapter(FormatVersion).validate_python(0)

    def test_enum_wire_boundary_returns_enum_and_rejects_unknown(self) -> None:
        for enum in (SnapshotChainKind, ArtifactKind, SnapshotApplyOutcomeKind):
            adapter = TypeAdapter(enum)
            for member in enum:
                with self.subTest(enum=enum, member=member):
                    self.assertIs(adapter.validate_json(adapter.dump_json(member), strict=True), member)
                    with self.assertRaises(ValidationError):
                        adapter.validate_python(member.value, strict=True)
            with self.assertRaises(ValidationError):
                adapter.validate_json('"unknown"', strict=True)

    def test_snapshot_chain_is_not_inferred_from_snapshot_id(self) -> None:
        adapter = TypeAdapter(SnapshotRef)
        self.assertIsInstance(adapter.validate_json(self.world.model_dump_json()), WorldSnapshotRef)
        self.assertIsInstance(adapter.validate_json(self.player.model_dump_json()), PlayerSnapshotRef)
        self.assertEqual(self.world.snapshot_id, self.player.snapshot_id)
        with self.assertRaises(ValidationError):
            WorldSnapshotRef.model_validate(self.player)
        for payload in (
            '{"kind":"unknown","snapshot_id":"tick-1"}',
            '{"snapshot_id":"tick-1","player_uid":"player"}',
            '{"kind":"world","world_uid":"world","timeline_id":"main",'
            '"snapshot_id":"tick-1","player_uid":"player"}',
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                adapter.validate_json(payload)

    def test_uid_and_hash_validation_does_not_normalize_or_invent_identity(self) -> None:
        for uid in ("", " world", "world ", 10, b"world", None):
            with self.subTest(uid=uid), self.assertRaises(ValidationError):
                WorldSnapshotRef.model_validate({**self.world.model_dump(), "world_uid": uid})
        for digest in ("A" * 64, "g" * 64, "a" * 63, "a" * 65, b"a" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                ArtifactRef.model_validate({**self.artifact.model_dump(), "content_hash": digest})

    def test_artifact_representation_shape_and_no_storage_handles(self) -> None:
        blob = ArtifactRef(
            kind=ArtifactKind.BLOB, format_key=self.format_key, format_version=1,
            content_hash="b" * 64, nbytes=0,
        )
        self.assertIsNone(blob.row_count)
        for field, value in (
            ("row_count", None), ("row_count", True), ("row_count", -1),
            ("nbytes", True), ("nbytes", -1), ("format_version", False),
            ("kind", "sql_rows"), ("path", "mutable/file"),
            ("table_name", "region_states"), ("callback", lambda: None),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ArtifactRef.model_validate({**self.artifact.model_dump(), field: value})
        with self.assertRaises(ValidationError):
            ArtifactRef.model_validate({**blob.model_dump(), "row_count": 0})
        # Membership, hash verification and backend selection need the explicit
        # application binding. Constructing a ref must not query such a registry.
        self.assertEqual(self.artifact.format_key, self.format_key)

    def test_publication_root_pack_and_first_tick_shapes(self) -> None:
        root = WorldPublicationRef(
            world_uid="world", publication_id="root", pack_hash=None,
            snapshot_head=None, active_timeline_id=None, gameplay_started=False,
        )
        started = WorldPublicationRef(
            world_uid="world", publication_id="started", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id="main", gameplay_started=True,
        )
        self.assertIsNone(root.snapshot_head)
        self.assertIsNone(started.snapshot_head)  # Start is not a fake snapshot.
        for changes in (
            {"pack_hash": None}, {"active_timeline_id": None},
            {"gameplay_started": 1}, {"gameplay_started": False, "snapshot_head": self.world},
            {"snapshot_head": self.world.model_copy(update={"world_uid": "another"})},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                WorldPublicationRef.model_validate({**started.model_dump(), **changes})

    def test_branch_ancestry_is_not_fabricated_by_reference_model(self) -> None:
        ref = WorldPublicationRef(
            world_uid="world", publication_id="branch-start", pack_hash="a" * 64,
            snapshot_head=self.world, active_timeline_id="branch", gameplay_started=True,
        )
        self.assertNotEqual(ref.active_timeline_id, ref.snapshot_head.timeline_id)
        # Whether this is an accepted branch point is a storage/ancestry guard,
        # not a model lookup or a requirement to generate a new snapshot.

    def test_player_expectation_distinguishes_absence_and_wrong_owner(self) -> None:
        absent = PlayerHeadExpectation(player_uid="player", expected_head=None)
        self.assertIsNone(absent.expected_head)
        with self.assertRaises(ValidationError):
            PlayerHeadExpectation(player_uid="another", expected_head=self.player)
        with self.assertRaises(ValidationError):
            PlayerHeadExpectation.model_validate({"player_uid": "player"})

    def test_state_and_history_refs_are_distinct_for_either_chain(self) -> None:
        for snapshot in (self.world, self.player):
            values = {"snapshot": snapshot, "section_key": self.section_key, "format_version": 1}
            state = SectionStateRef.model_validate(values)
            history = SectionHistoryRef.model_validate(values)
            self.assertNotEqual(state, history)
            with self.assertRaises(ValidationError):
                SectionHistoryRef.model_validate(state)
            with self.assertRaises(ValidationError):
                SectionStateRef.model_validate(history)

    def test_registry_declarations_reject_duplicates_empty_versions_and_mutability(self) -> None:
        for registry, metadata, key in (
            (PatchSectionRegistry, PatchSectionMetadata, self.section_key),
            (ArtifactFormatRegistry, ArtifactFormatMetadata, self.format_key),
        ):
            entry = metadata.model_validate({"key": key, "supported_versions": frozenset({1, 2})})
            self.assertEqual(registry.model_validate({"entries": ()}).entries, ())
            with self.assertRaises(ValidationError):
                registry.model_validate({"entries": (entry, entry)})
            for versions in (frozenset(), frozenset({True}), frozenset({0}), {1}, [1]):
                with self.subTest(registry=registry, versions=versions), self.assertRaises(ValidationError):
                    metadata.model_validate({"key": key, "supported_versions": versions})
            with self.assertRaises(ValidationError):
                registry.model_validate({"entries": [entry]})

    def test_all_records_are_frozen_strict_and_round_trip(self) -> None:
        section = PatchSectionMetadata(key=self.section_key, supported_versions=frozenset({1}))
        artifact_format = ArtifactFormatMetadata(key=self.format_key, supported_versions=frozenset({1}))
        records: tuple[BaseModel, ...] = (
            self.world, self.player, self.artifact, section, artifact_format,
            PatchSectionRegistry(entries=(section,)), ArtifactFormatRegistry(entries=(artifact_format,)),
            PlayerHeadExpectation(player_uid="player", expected_head=self.player),
            WorldPublicationRef(world_uid="world", publication_id="p", pack_hash="a" * 64,
                                snapshot_head=self.world, active_timeline_id="main", gameplay_started=True),
            SectionStateRef(snapshot=self.world, section_key=self.section_key, format_version=1),
            SectionHistoryRef(snapshot=self.player, section_key=self.section_key, format_version=1),
        )
        for record in records:
            with self.subTest(model=type(record).__name__):
                self.assertEqual(type(record).model_validate_json(record.model_dump_json()), record)
                with self.assertRaises(ValidationError):
                    setattr(record, next(iter(type(record).model_fields)), None)
                with self.assertRaises(ValidationError):
                    type(record).model_validate({**record.model_dump(), "unexpected": True})

    def test_nested_constructed_instances_are_revalidated(self) -> None:
        invalid = WorldSnapshotRef.model_construct(world_uid="", timeline_id="main", snapshot_id="s")
        with self.assertRaises(ValidationError):
            SectionStateRef(snapshot=invalid, section_key=self.section_key, format_version=1)
        invalid_metadata = PatchSectionMetadata.model_construct(
            key=self.section_key, supported_versions=frozenset({0}),
        )
        with self.assertRaises(ValidationError):
            PatchSectionRegistry(entries=(invalid_metadata,))

    def test_patch_header_rejects_duplicate_refs_and_self_dependency(self) -> None:
        ref = PatchRef(operation_id="op", section_key=self.section_key, ordinal=0)
        previous = PatchRef(operation_id="op", section_key=self.section_key, ordinal=1)
        values = dict(ref=ref, format_version=1, depends_on=(previous,), artifacts=(self.artifact,))
        header = PatchHeader.model_validate(values)
        self.assertEqual(PatchHeader.model_validate_json(header.model_dump_json()), header)
        for changes in ({"depends_on": (ref,)}, {"depends_on": (previous, previous)},
                        {"artifacts": (self.artifact, self.artifact)}, {"artifacts": []},
                        {"depends_on": []}, {"callback": lambda: None}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PatchHeader.model_validate({**values, **changes})

    def test_section_dependency_identity_and_generic_binding(self) -> None:
        state = SectionStateRef(snapshot=self.world, section_key=self.section_key, format_version=1)
        dependencies = (
            PreparedSectionDependency(section_key=RegistryKey[PatchSectionRegistry]("earlier"),
                                      section_fingerprint="a" * 64),
            PublishedSectionDependency(section_ref=state),
        )
        for dep in dependencies:
            self.assertEqual(TypeAdapter(SectionDependency).validate_json(dep.model_dump_json()), dep)
        header = SectionHeader(key=self.section_key, format_version=1, depends_on=dependencies)
        patch = PatchHeader(ref=PatchRef(operation_id="op", section_key=self.section_key, ordinal=0),
                            format_version=1, depends_on=(), artifacts=())
        # Structural fixtures only: these headers are not production domain patches.
        section_type = DomainSection[PatchHeader]
        section = section_type(header=header, patches=(patch,))
        self.assertEqual(section_type.model_validate_json(section.model_dump_json()), section)
        for patches in ((), [], (self.artifact,), ({"untyped": "payload"},)):
            with self.subTest(patches=patches), self.assertRaises(ValidationError):
                section_type.model_validate({"header": header, "patches": patches})
        for deps in ((dependencies[0], dependencies[0]),
                     (PreparedSectionDependency(section_key=self.section_key, section_fingerprint="a" * 64),)):
            with self.subTest(deps=deps), self.assertRaises(ValidationError):
                SectionHeader(key=self.section_key, format_version=1, depends_on=deps)

    def test_runtime_request_preserves_order_and_allows_explicit_empty_tick(self) -> None:
        publication = WorldPublicationRef(
            world_uid="world", publication_id="p", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id="main", gameplay_started=True,
        )
        values = dict(format_version=1, operation_id="op", preparation_fingerprint="b" * 64,
                      world_uid="world", timeline_id="main", turn_id=1, expected_world=publication,
                      expected_players=(), sections=())
        request_type = PatchSet[DomainSection[PatchHeader]]
        empty = request_type.model_validate(values)
        self.assertEqual(request_type.model_validate_json(empty.model_dump_json()), empty)
        sections = tuple(DomainSection[PatchHeader](
            header=SectionHeader(key=RegistryKey[PatchSectionRegistry](key), format_version=1, depends_on=()),
            patches=(PatchHeader(ref=PatchRef(operation_id="op", section_key=RegistryKey[PatchSectionRegistry](key),
                                              ordinal=0), format_version=1, depends_on=(), artifacts=()),),
        ) for key in ("z", "a"))
        request = request_type.model_validate({**values, "sections": sections})
        self.assertEqual(tuple(section.header.key for section in request.sections), ("z", "a"))
        player = PlayerHeadExpectation(player_uid="player", expected_head=None)
        for changes in ({"turn_id": True}, {"turn_id": 0}, {"turn_id": "1"},
                        {"expected_players": (player, player)}, {"sections": (sections[0], sections[0])},
                        {"sections": []}, {"world_uid": "another"},
                        {"expected_world": publication.model_copy(update={"pack_hash": None,
                                                                         "gameplay_started": False})}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                request_type.model_validate({**values, **changes})

    def test_absence_tombstone_and_runtime_versions_remain_distinct(self) -> None:
        pack = PackTargetVersion(pack_hash="a" * 64, artifact=self.artifact)
        versions = (pack, SnapshotTargetVersion(snapshot=self.world), SnapshotTargetVersion(snapshot=self.player))
        adapter = TypeAdapter(RuntimeTargetExpectation)
        records = [TargetAbsent()]
        records.extend(TargetVersionExpected(version=version, presence=presence)
                       for version in versions for presence in TargetPresence)
        for record in records:
            self.assertEqual(adapter.validate_json(record.model_dump_json()), record)
            with self.assertRaises(ValidationError):
                setattr(record, "kind", None)
        for payload in ('{"kind":"absent","presence":"deleted"}',
                        '{"kind":"version","presence":"deleted"}', '{"kind":"unknown"}',
                        '{"kind":"version","version":{"kind":"source"},"presence":"present"}'):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                adapter.validate_json(payload)
        with self.assertRaises(ValidationError):
            TargetVersionExpected(version=pack, presence="deleted")

    def test_section_refusal_is_typed_and_does_not_publish(self) -> None:
        diagnostic = FieldPathError(path=("target",), message="stale target", code="arbitrary")
        adapter = TypeAdapter(SectionValidation)
        for record in (SectionAccepted(), *(SectionRefused(category=category, diagnostics=(diagnostic,))
                       for category in (SnapshotApplyOutcomeKind.CONFLICT, SnapshotApplyOutcomeKind.REJECTED))):
            self.assertEqual(adapter.validate_json(record.model_dump_json()), record)
        for changes in ({"category": SnapshotApplyOutcomeKind.COMMITTED}, {"category": "conflict"},
                        {"diagnostics": ()}, {"diagnostics": []}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SectionRefused.model_validate({"category": SnapshotApplyOutcomeKind.CONFLICT,
                                              "diagnostics": (diagnostic,), **changes})
        with self.assertRaises(ValidationError):
            adapter.validate_python({"category": SnapshotApplyOutcomeKind.CONFLICT})

    def test_receipt_chain_uniqueness_and_section_ownership(self) -> None:
        history = SectionHistoryRef(snapshot=self.world, section_key=self.section_key, format_version=1)
        state = SectionStateRef(snapshot=self.world, section_key=self.section_key, format_version=1)
        changed = PatchRef(operation_id="op", section_key=self.section_key, ordinal=0)
        values = dict(section_key=self.section_key, history_refs=(history,), state_refs=(state,),
                      changed=(), retained_artifacts=())
        receipt = SectionApplyReceipt.model_validate(values)
        self.assertEqual(SectionApplyReceipt.model_validate_json(receipt.model_dump_json()), receipt)
        # A no-op may retain old state and still write history; comparisons to
        # the captured base and declared participants belong to application.
        later = self.world.model_copy(update={"snapshot_id": "tick-2"})
        for changes in (
            {"state_refs": (state, state.model_copy(update={"snapshot": later}))},
            {"history_refs": (history, history)}, {"changed": (changed, changed)},
            {"section_key": RegistryKey[PatchSectionRegistry]("other")},
            {"state_refs": (history,)}, {"retained_artifacts": (self.artifact, self.artifact)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SectionApplyReceipt.model_validate({**values, **changes})

    def test_reference_packages_have_no_io_or_executable_registration(self) -> None:
        source_root = Path(__file__).resolve().parents[3] / "app" / "dataModel"
        forbidden = ("app.application", "app.db", "app.core", "app.storage", "logging")
        for namespace in ("patch", "artifacts", "worldSnapshot"):
            for source in (source_root / namespace).rglob("*.py"):
                module = ast.parse(source.read_text(encoding="utf-8"))
                with self.subTest(source=source):
                    if source.name == "__init__.py":
                        self.assertEqual(module.body, [])
                    for node in ast.walk(module):
                        imports = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                                   [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                        self.assertFalse(any(name == prefix or name.startswith(prefix + ".")
                                             for name in imports for prefix in forbidden))

    def test_core_dtos_only_import_data_and_pure_validation_dependencies(self) -> None:
        source_root = Path(__file__).resolve().parents[3] / "app" / "dataModel"
        allowed = ("__future__", "enum", "typing", "datetime", "pydantic", "app.dataModel")
        for namespace in ("patch", "artifacts", "worldSnapshot"):
            for source in (source_root / namespace).rglob("*.py"):
                module = ast.parse(source.read_text(encoding="utf-8"))
                for node in ast.walk(module):
                    imports = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                               [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for name in imports:
                        with self.subTest(source=source, imported=name):
                            self.assertTrue(any(name == prefix or name.startswith(prefix + ".") for prefix in allowed))
                    if isinstance(node, ast.Call):
                        name = (node.func.attr if isinstance(node.func, ast.Attribute) else
                                node.func.id if isinstance(node.func, ast.Name) else None)
                        with self.subTest(source=source, call=name):
                            self.assertNotIn(name, ("now", "utcnow", "today", "open", "read_text", "write_text",
                                                    "getLogger", "emit", "commit", "execute"))

    def test_patch_records_are_frozen_and_revalidate_nested_instances(self) -> None:
        ref = PatchRef(operation_id="op", section_key=self.section_key, ordinal=0)
        patch = PatchHeader(ref=ref, format_version=1, depends_on=(), artifacts=())
        header = SectionHeader(key=self.section_key, format_version=1, depends_on=())
        section = DomainSection[PatchHeader](header=header, patches=(patch,))
        publication = WorldPublicationRef(world_uid="world", publication_id="p", pack_hash="a" * 64,
                                          snapshot_head=None, active_timeline_id="main", gameplay_started=True)
        state = SectionStateRef(snapshot=self.world, section_key=self.section_key, format_version=1)
        pack = PackTargetVersion(pack_hash="a" * 64, artifact=self.artifact)
        records = (
            ref, patch, header, section,
            PreparedSectionDependency(section_key=self.section_key, section_fingerprint="a" * 64),
            PublishedSectionDependency(section_ref=state), pack, SnapshotTargetVersion(snapshot=self.player),
            TargetAbsent(), TargetVersionExpected(version=pack, presence=TargetPresence.PRESENT),
            SectionAccepted(), SectionRefused(category=SnapshotApplyOutcomeKind.REJECTED,
                                              diagnostics=(FieldPathError(path=(), message="invalid"),)),
            SectionApplyReceipt(section_key=self.section_key, history_refs=(), state_refs=(),
                                changed=(), retained_artifacts=()),
            PatchSet[DomainSection[PatchHeader]](
                format_version=1, operation_id="op", preparation_fingerprint="b" * 64,
                world_uid="world", timeline_id="main", turn_id=1, expected_world=publication,
                expected_players=(), sections=(section,),
            ),
        )
        for record in records:
            with self.subTest(model=type(record).__name__):
                self.assertEqual(type(record).model_validate_json(record.model_dump_json()), record)
                with self.assertRaises(ValidationError):
                    type(record).model_validate({**record.model_dump(), "unexpected": True})
                if type(record).model_fields:
                    with self.assertRaises(ValidationError):
                        setattr(record, next(iter(type(record).model_fields)), None)
        invalid = patch.model_copy(update={"ref": ref.model_copy(update={"ordinal": -1})})
        with self.assertRaises(ValidationError):
            DomainSection[PatchHeader](header=header, patches=(invalid,))


    def _snapshot_dto_fixtures(self):
        publication = WorldPublicationRef(
            world_uid="world", publication_id="commit", pack_hash="a" * 64,
            snapshot_head=self.world, active_timeline_id=self.world.timeline_id, gameplay_started=True,
        )
        commit = SnapshotCommitRefs(world_snapshot=self.world, player_snapshots=(self.player,),
                                    publication=publication)
        diagnostic = FieldPathError(path=("target", 0), message="stale")
        success = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.COMMITTED, operation_id="op",
                                      request_fingerprint="b" * 64, committed=commit, diagnostics=())
        refusal = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.CONFLICT, operation_id="op",
                                      request_fingerprint="b" * 64, committed=None, diagnostics=(diagnostic,))
        lease = OperationLeaseRef(operation_id="op", world_uid="world", kind=OperationKind.SNAPSHOT_APPLY,
                                  preparation_fingerprint="c" * 64, fence=1)
        ready = OperationRecord(**lease.model_dump(), publication_fingerprint=None,
                                phase=OperationPhase.READY, leased_artifacts=(self.artifact,), terminal=None)
        terminal = OperationRecord.model_validate({**ready.model_dump(), "phase": OperationPhase.TERMINAL,
                                                   "publication_fingerprint": "b" * 64, "terminal": success})
        return publication, commit, diagnostic, success, refusal, lease, ready, terminal

    def test_metadata_chain_ownership_history_and_retained_state(self) -> None:
        old_world = self.world.model_copy(update={"timeline_id": "old", "snapshot_id": "old"})
        old_player = self.player.model_copy(update={"snapshot_id": "old"})
        for model, ref, old in ((WorldSnapshotMetadata, self.world, old_world),
                                (PlayerSnapshotMetadata, self.player, old_player)):
            values = dict(ref=ref, parent=old, operation_id="op", turn_id=1,
                          created_at="2026-10-30T01:02:03.123456Z", envelope_format_version=1,
                          state_refs=(SectionStateRef(snapshot=old, section_key=self.section_key, format_version=1),),
                          history_refs=(SectionHistoryRef(snapshot=ref, section_key=self.section_key, format_version=1),),
                          retained_artifacts=(self.artifact,))
            if model is WorldSnapshotMetadata:
                values["base_pack_hash"] = "a" * 64
            record = model.model_validate(values)
            self.assertEqual(TypeAdapter(SnapshotEnvelope).validate_json(record.model_dump_json()), record)
            # A first tick has no fake parent; old state may survive while history advances.
            model.model_validate({**values, "parent": None})
            wrong = self.player if model is WorldSnapshotMetadata else self.world
            for changes in (
                {"ref": wrong}, {"parent": wrong}, {"parent": ref},
                {"state_refs": (SectionStateRef(snapshot=wrong, section_key=self.section_key, format_version=1),)},
                {"history_refs": (SectionHistoryRef(snapshot=old, section_key=self.section_key, format_version=1),)},
                {"state_refs": (values["state_refs"][0],) * 2},
                {"history_refs": (values["history_refs"][0],) * 2},
                {"state_refs": values["history_refs"]}, {"turn_id": True}, {"turn_id": 0},
                {"retained_artifacts": (self.artifact, self.artifact)}, {"state_refs": []},
            ):
                with self.subTest(model=model, changes=changes), self.assertRaises(ValidationError):
                    model.model_validate({**values, **changes})
            owner_field = "world_uid" if model is WorldSnapshotMetadata else "player_uid"
            with self.assertRaises(ValidationError):
                model.model_validate({**values, "parent": old.model_copy(update={owner_field: "another"})})

    def test_created_at_is_strict_calendar_utc_wire_without_clock(self) -> None:
        adapter = TypeAdapter(CreatedAtUtc)
        for value in ("2024-02-29T23:59:59.000000Z", "0001-01-01T00:00:00.123456Z"):
            self.assertEqual(adapter.validate_python(value), value)
            self.assertEqual(adapter.validate_json('"' + value + '"'), value)
        for value in ("2026-02-29T00:00:00.000000Z", "2026-04-31T00:00:00.000000Z",
                      "2026-10-30T24:00:00.000000Z", "2026-10-30T00:00:60.000000Z",
                      "2026-10-30T00:00:00.0Z", "2026-10-30T00:00:00.000000+00:00",
                      "0000-01-01T00:00:00.000000Z", "2026-10-30T00:00:00.000000Z\n", 123, True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_apply_result_category_commit_and_diagnostic_invariants(self) -> None:
        publication, commit, diagnostic, success, refusal, *_ = self._snapshot_dto_fixtures()
        for category in SnapshotApplyOutcomeKind:
            for committed in (None, commit):
                for diagnostics in ((), (diagnostic,)):
                    values = dict(category=category, operation_id="op", request_fingerprint="b" * 64,
                                  committed=committed, diagnostics=diagnostics)
                    valid = ((category is SnapshotApplyOutcomeKind.COMMITTED and committed is not None
                              and not diagnostics) or (category is not SnapshotApplyOutcomeKind.COMMITTED
                              and committed is None and bool(diagnostics)))
                    if valid:
                        record = SnapshotApplyResult.model_validate(values)
                        self.assertEqual(SnapshotApplyResult.model_validate_json(record.model_dump_json()), record)
                    else:
                        with self.assertRaises(ValidationError):
                            SnapshotApplyResult.model_validate(values)
        for changes in ({"category": "committed"}, {"diagnostics": []}, {"request_fingerprint": "bad"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SnapshotApplyResult.model_validate({**success.model_dump(), **changes})
        for changes in ({"world_snapshot": self.player}, {"player_snapshots": (self.world,)},
                        {"player_snapshots": (self.player, self.player.model_copy(update={"snapshot_id": "other"}))},
                        {"publication": publication.model_copy(update={"snapshot_head": None})},
                        {"publication": publication.model_copy(update={"active_timeline_id": "other"})}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SnapshotCommitRefs.model_validate({**commit.model_dump(), **changes})

    def test_pregame_outcomes_do_not_create_snapshot_ticks(self) -> None:
        publication, _, _, success, *_ = self._snapshot_dto_fixtures()
        pregame = WorldPublicationRef(world_uid="world", publication_id="pack", pack_hash=self.artifact.content_hash,
                                     snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        active = PackActivationResult(operation_id="op", request_fingerprint="b" * 64, manifest=self.artifact,
                                      disposition=PackActivationDisposition.ACTIVE, publication=pregame)
        inactive = PackActivationResult.model_validate({**active.model_dump(),
            "disposition": PackActivationDisposition.READY_INACTIVE, "publication": publication})
        start_publication = publication.model_copy(update={"snapshot_head": None})
        started = GameplayStarted(operation_id="op", request_fingerprint="b" * 64, publication=start_publication)
        for model, values in (
            (PackActivationResult, {**active.model_dump(), "publication": publication}),
            (PackActivationResult, {**active.model_dump(), "publication": pregame.model_copy(update={"pack_hash": "f" * 64})}),
            (GameplayStarted, {**started.model_dump(), "publication": publication}),
            (GameplayStarted, {**started.model_dump(), "publication": pregame}),
        ):
            with self.subTest(model=model), self.assertRaises(ValidationError):
                model.model_validate(values)
        self.assertNotEqual(type(inactive), type(success))
        for record in (active, inactive, started):
            self.assertEqual(type(record).model_validate_json(record.model_dump_json()), record)

    def test_operation_phase_terminal_and_binding_matrix(self) -> None:
        _, _, diagnostic, success, refusal, _, ready, terminal = self._snapshot_dto_fixtures()
        cancelled = OperationCancelled(operation_id="op", reason=diagnostic)
        for phase in OperationPhase:
            for result in (None, success, refusal, cancelled):
                values = {**terminal.model_dump(), "phase": phase, "terminal": result}
                valid = (phase is OperationPhase.TERMINAL) == (result is not None)
                if valid:
                    OperationRecord.model_validate(values)
                else:
                    with self.assertRaises(ValidationError):
                        OperationRecord.model_validate(values)
        for kind in OperationKind:
            OperationRecord.model_validate({**terminal.model_dump(), "kind": kind, "terminal": refusal})
            OperationRecord.model_validate({**ready.model_dump(), "kind": kind,
                                            "phase": OperationPhase.TERMINAL, "terminal": cancelled})
        for changes in (
            {"phase": OperationPhase.APPLYING, "publication_fingerprint": None},
            {"fence": True}, {"fence": 0}, {"phase": "ready"}, {"kind": "snapshot_apply"},
            {"leased_artifacts": (self.artifact, self.artifact)}, {"leased_artifacts": []},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                OperationRecord.model_validate({**ready.model_dump(), **changes})
        for changes in ({"kind": OperationKind.PACK_ACTIVATION}, {"world_uid": "other"},
                        {"operation_id": "other"}, {"publication_fingerprint": "f" * 64},
                        {"publication_fingerprint": None}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                OperationRecord.model_validate({**terminal.model_dump(), **changes})

    def test_operation_pregame_terminal_kind_and_world_matrix(self) -> None:
        publication, _, _, _, _, _, _, terminal = self._snapshot_dto_fixtures()
        started = GameplayStarted(operation_id="op", request_fingerprint="b" * 64,
                                  publication=publication.model_copy(update={"snapshot_head": None}))
        activation = PackActivationResult(operation_id="op", request_fingerprint="b" * 64,
            publication=publication, manifest=self.artifact, disposition=PackActivationDisposition.READY_INACTIVE)
        for result, expected in ((started, OperationKind.GAMEPLAY_START), (activation, OperationKind.PACK_ACTIVATION)):
            for kind in OperationKind:
                values = {**terminal.model_dump(), "kind": kind, "terminal": result}
                if kind is expected:
                    record = OperationRecord.model_validate(values)
                    self.assertEqual(OperationRecord.model_validate_json(record.model_dump_json()), record)
                    with self.assertRaises(ValidationError):
                        OperationRecord.model_validate({**values, "world_uid": "other"})
                else:
                    with self.assertRaises(ValidationError):
                        OperationRecord.model_validate(values)

    def test_operation_claim_discriminator_and_busy_are_not_refusals(self) -> None:
        *_, lease, ready, terminal = self._snapshot_dto_fixtures()
        adapter = TypeAdapter(OperationClaim)
        for record in (PublicationOwner(lease=lease), PublicationBusy(record=ready), PublicationTerminal(record=terminal)):
            self.assertEqual(adapter.validate_json(record.model_dump_json()), record)
        for model, record in ((PublicationBusy, terminal), (PublicationTerminal, ready)):
            with self.assertRaises(ValidationError):
                model(record=record)
        for value in ('{"kind":"conflict"}', '{"kind":"owner","record":{}}', '{"kind":"unknown"}'):
            with self.assertRaises(ValidationError):
                adapter.validate_json(value)

    def test_artifact_holder_discriminators_fences_and_gc_disjointness(self) -> None:
        *_, lease, _, _ = self._snapshot_dto_fixtures()
        holders = (OperationHolder(lease=lease), ArtifactRetentionHolder(artifact=self.artifact),
                   SnapshotHolder(snapshot=self.world), SnapshotHolder(snapshot=self.player))
        adapter = TypeAdapter(ArtifactHolderRef)
        for holder in holders:
            self.assertEqual(adapter.validate_json(holder.model_dump_json()), holder)
            verified = VerifiedArtifactRef(ref=self.artifact, holder=holder)
            self.assertEqual(VerifiedArtifactRef.model_validate_json(verified.model_dump_json()), verified)
        for changes in ({"fence": 0}, {"fence": True}, {"fence": "1"}, {"kind": OperationClaimKind.OWNER}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                OperationLeaseRef.model_validate({**lease.model_dump(), **changes})
        for payload in ('{"kind":"snapshot_apply"}', '{"kind":"snapshot","snapshot":{"kind":"unknown"}}'):
            with self.assertRaises(ValidationError):
                adapter.validate_json(payload)
        for changes in ({"deleted": (self.artifact,), "retained": (self.artifact,)},
                        {"deleted": (self.artifact, self.artifact)}, {"retained": (self.artifact, self.artifact)},
                        {"deleted": []}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                GcReport.model_validate({"deleted": (), "retained": (), "failed": (), **changes})

    def test_logging_dtos_are_typed_context_without_payload_or_delivery(self) -> None:
        values = dict(operation_id="op", world_uid="world", request_fingerprint="b" * 64,
                      timeline_id=None, snapshot_id=None, section_key=None, outcome=None)
        outcomes = {SnapshotLogActivity.APPLY_COMMITTED: SnapshotApplyOutcomeKind.COMMITTED,
                    SnapshotLogActivity.APPLY_CONFLICT: SnapshotApplyOutcomeKind.CONFLICT,
                    SnapshotLogActivity.APPLY_REJECTED: SnapshotApplyOutcomeKind.REJECTED}
        for activity in SnapshotLogActivity:
            outcome = outcomes.get(activity)
            record = SnapshotLogRecord(activity=activity, **{**values, "outcome": outcome})
            self.assertEqual(SnapshotLogRecord.model_validate_json(record.model_dump_json()), record)
            if outcome is not None:
                for changes in ({"outcome": None}, {"outcome": "committed"}, {"request_fingerprint": None}):
                    with self.assertRaises(ValidationError):
                        SnapshotLogRecord.model_validate({**record.model_dump(), **changes})
        for activity in ArtifactLogActivity:
            record = ArtifactLogRecord(activity=activity, operation_id="maintenance", world_uid=None,
                preparation_fingerprint=None, request_fingerprint=None, artifact_hash=None)
            self.assertEqual(ArtifactLogRecord.model_validate_json(record.model_dump_json()), record)
        for changes in ({"activity": "apply_started"}, {"payload": {}}, {"logger": object()},
                        {"outcome": SnapshotApplyOutcomeKind.COMMITTED}):
            with self.assertRaises(ValidationError):
                SnapshotLogRecord.model_validate({**values, "activity": SnapshotLogActivity.APPLY_STARTED, **changes})

    def test_new_dtos_frozen_strict_roundtrip_and_nested_revalidation(self) -> None:
        publication, commit, diagnostic, success, refusal, lease, ready, terminal = self._snapshot_dto_fixtures()
        metadata = WorldSnapshotMetadata(ref=self.world, parent=None, operation_id="op", turn_id=1,
            created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1, base_pack_hash="a" * 64,
            state_refs=(), history_refs=(), retained_artifacts=())
        player = PlayerSnapshotMetadata(**{key: value for key, value in metadata.model_dump().items()
                                          if key not in ("ref", "base_pack_hash")}, ref=self.player)
        records = (metadata, player, commit, success, refusal, lease, ready, terminal,
            OperationCancelled(operation_id="op", reason=diagnostic),
            StagingReservation(artifact_id="artifact", lease=lease, ref=self.artifact),
            PublicationOwner(lease=lease), PublicationBusy(record=ready), PublicationTerminal(record=terminal),
            OperationHolder(lease=lease), ArtifactRetentionHolder(artifact=self.artifact), SnapshotHolder(snapshot=self.player),
            VerifiedArtifactRef(ref=self.artifact, holder=SnapshotHolder(snapshot=self.world)),
            GcReport(deleted=(), retained=(self.artifact,), failed=(diagnostic,)),
            ArtifactLogRecord(activity=ArtifactLogActivity.GC_FAILED, operation_id="gc", world_uid=None,
                              preparation_fingerprint=None, request_fingerprint=None, artifact_hash=None),
            SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_STARTED, operation_id="op", world_uid="world",
                request_fingerprint=None, timeline_id=None, snapshot_id=None, section_key=None, outcome=None),
            GameplayStarted(operation_id="op", request_fingerprint="b" * 64,
                            publication=publication.model_copy(update={"snapshot_head": None})),
            PackActivationResult(operation_id="op", request_fingerprint="b" * 64, manifest=self.artifact,
                                  disposition=PackActivationDisposition.READY_INACTIVE, publication=publication),
        )
        for record in records:
            with self.subTest(model=type(record).__name__):
                self.assertEqual(type(record).model_validate_json(record.model_dump_json()), record)
                with self.assertRaises(ValidationError):
                    setattr(record, next(iter(type(record).model_fields)), None)
                with self.assertRaises(ValidationError):
                    type(record).model_validate({**record.model_dump(), "extra": True})
                # model_copy/construct can bypass validation; every nested boundary must revalidate.
                invalid = record.model_copy(update={next(iter(type(record).model_fields)): object()})
                with self.assertRaises(ValidationError):
                    TypeAdapter(type(record)).validate_python(invalid)
        invalid_lease = lease.model_copy(update={"fence": 0})
        with self.assertRaises(ValidationError):
            OperationHolder(lease=invalid_lease)
        invalid_terminal = terminal.model_copy(update={"terminal": None})
        with self.assertRaises(ValidationError):
            PublicationTerminal(record=invalid_terminal)
        for enum in (OperationKind, OperationPhase, OperationClaimKind, PackActivationDisposition,
                     CasDecision, ArtifactStorageEventKind, SnapshotLogActivity, ArtifactLogActivity):
            with self.assertRaises(ValidationError):
                TypeAdapter(enum).validate_json('"unknown"')
            for value in enum:
                self.assertIs(TypeAdapter(enum).validate_json('"' + value.value + '"'), value)


    def test_snapshot_emitter_activity_levels_and_common_facade_correlation(self) -> None:
        outcomes = {
            SnapshotLogActivity.APPLY_COMMITTED: SnapshotApplyOutcomeKind.COMMITTED,
            SnapshotLogActivity.APPLY_CONFLICT: SnapshotApplyOutcomeKind.CONFLICT,
            SnapshotLogActivity.APPLY_REJECTED: SnapshotApplyOutcomeKind.REJECTED,
        }
        levels = {
            SnapshotLogActivity.APPLY_STARTED: logging.DEBUG,
            SnapshotLogActivity.APPLY_COMMITTED: logging.INFO,
            SnapshotLogActivity.APPLY_CONFLICT: logging.WARNING,
            SnapshotLogActivity.APPLY_REJECTED: logging.WARNING,
            SnapshotLogActivity.APPLY_FAILED: logging.ERROR,
            SnapshotLogActivity.APPLY_OUTCOME_UNKNOWN: logging.ERROR,
            SnapshotLogActivity.OPERATION_BUSY: logging.DEBUG,
            SnapshotLogActivity.OPERATION_RECOVERED: logging.INFO,
        }
        token = request_id_var.set("request-correlation")
        try:
            for activity in SnapshotLogActivity:
                event = SnapshotLogRecord(activity=activity, operation_id="op", world_uid="world",
                    request_fingerprint="a" * 64, timeline_id="main", snapshot_id="tick",
                    section_key=self.section_key, outcome=outcomes.get(activity))
                with self.subTest(activity=activity), self.assertLogs("app.snapshot", level="DEBUG") as captured:
                    SnapshotLifecycleLog().emit(event)
                self.assertEqual(len(captured.records), 1)
                record = captured.records[0]
                self.assertEqual(record.name, "app.snapshot")
                self.assertEqual(record.levelno, levels[activity])
                fields = json.loads(JsonLogFormatter().format(record))
                self.assertEqual(fields["request_id"], "request-correlation")
                for name, value in event.model_dump(mode="json").items():
                    self.assertEqual(fields[name], value)
                self.assertNotIn("request_id", event.model_dump())
                self.assertNotIn("diagnostics", fields)
                self.assertNotIn("payload", fields)
        finally:
            request_id_var.reset(token)

    def test_artifact_emitter_levels_context_and_global_gc_absence(self) -> None:
        levels = {ArtifactLogActivity.ARTIFACT_SEALED: logging.DEBUG,
                  ArtifactLogActivity.LEASE_RELEASED: logging.INFO,
                  ArtifactLogActivity.GC_DELETED: logging.INFO,
                  ArtifactLogActivity.GC_FAILED: logging.ERROR}
        for activity in ArtifactLogActivity:
            event = ArtifactLogRecord(activity=activity, operation_id="maintenance", world_uid=None,
                preparation_fingerprint="b" * 64, request_fingerprint=None, artifact_hash="a" * 64)
            with self.subTest(activity=activity), self.assertLogs("app.artifacts", level="DEBUG") as captured:
                ArtifactLifecycleLog().emit(event)
            self.assertEqual(len(captured.records), 1)
            record = captured.records[0]
            self.assertEqual(record.levelno, levels[activity])
            fields = json.loads(JsonLogFormatter().format(record))
            self.assertIsNone(fields["world_uid"])
            self.assertIsNone(fields["request_fingerprint"])
            for name, value in event.model_dump(mode="json").items():
                self.assertEqual(fields[name], value)

    def test_terminal_retry_event_and_unknown_outcome_never_add_a_commit_event(self) -> None:
        values = dict(operation_id="op", world_uid="world", request_fingerprint="a" * 64,
                      timeline_id=None, snapshot_id=None, section_key=None)
        emitter = SnapshotLifecycleLog()
        with self.assertLogs("app.snapshot", level="DEBUG") as captured:
            emitter.emit(SnapshotLogRecord(activity=SnapshotLogActivity.OPERATION_RECOVERED,
                outcome=SnapshotApplyOutcomeKind.COMMITTED, **values))
            emitter.emit(SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_OUTCOME_UNKNOWN,
                outcome=None, **values))
        self.assertEqual([record.activity for record in captured.records],
                         ["operation_recovered", "apply_outcome_unknown"])
        self.assertEqual([record.outcome for record in captured.records], ["committed", None])
        invalid = SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_STARTED, outcome=None, **values)
        invalid = invalid.model_copy(update={"activity": SnapshotLogActivity.APPLY_COMMITTED})
        with patch("app.application.worldSnapshot.logging.snapshotLog._LOGGER.log") as log:
            with self.assertRaises(ValidationError):
                emitter.emit(invalid)
            log.assert_not_called()

    def test_logging_delivery_failure_is_not_reemitted_and_preserves_typed_outcomes(self) -> None:
        event = SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_COMMITTED, operation_id="op", world_uid="world",
            request_fingerprint="a" * 64, timeline_id=None, snapshot_id=None, section_key=None,
            outcome=SnapshotApplyOutcomeKind.COMMITTED)
        artifact = ArtifactLogRecord(activity=ArtifactLogActivity.ARTIFACT_SEALED, operation_id="op", world_uid="world",
            preparation_fingerprint="b" * 64, request_fingerprint=None, artifact_hash="a" * 64)
        for emitter, record, target in (
            (SnapshotLifecycleLog(), event, "app.application.worldSnapshot.logging.snapshotLog._LOGGER.log"),
            (ArtifactLifecycleLog(), artifact, "app.application.artifacts.logging.artifactLog._LOGGER.log"),
        ):
            before = record.model_dump()
            with patch(target, side_effect=RuntimeError("sink unavailable")) as log:
                emitter.emit(record)
                log.assert_called_once()
            self.assertEqual(record.model_dump(), before)

    def test_emitters_reject_wrong_models_and_untyped_payloads_before_logging(self) -> None:
        event = SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_STARTED, operation_id="op", world_uid="world",
            request_fingerprint=None, timeline_id=None, snapshot_id=None, section_key=None, outcome=None)
        artifact = ArtifactLogRecord(activity=ArtifactLogActivity.GC_FAILED, operation_id="maintenance", world_uid=None,
            preparation_fingerprint=None, request_fingerprint=None, artifact_hash=None)
        for emitter, wrong, target in (
            (SnapshotLifecycleLog(), artifact, "app.application.worldSnapshot.logging.snapshotLog._LOGGER.log"),
            (SnapshotLifecycleLog(), event.model_dump(), "app.application.worldSnapshot.logging.snapshotLog._LOGGER.log"),
            (ArtifactLifecycleLog(), event, "app.application.artifacts.logging.artifactLog._LOGGER.log"),
            (ArtifactLifecycleLog(), artifact.model_dump(), "app.application.artifacts.logging.artifactLog._LOGGER.log"),
        ):
            with patch(target) as log:
                with self.assertRaises(TypeError):
                    emitter.emit(wrong)
                log.assert_not_called()

    def test_emitters_install_no_handlers_and_have_no_storage_or_lifecycle_state(self) -> None:
        for logger_name, emitter_type in (("app.snapshot", SnapshotLifecycleLog), ("app.artifacts", ArtifactLifecycleLog)):
            logger = logging.getLogger(logger_name)
            handlers = tuple(logger.handlers)
            emitter = emitter_type()
            self.assertEqual(tuple(logger.handlers), handlers)
            self.assertFalse(hasattr(emitter, "__dict__"))
        source_root = Path(__file__).resolve().parents[3] / "app" / "application"
        for relative in ("worldSnapshot/logging/snapshotLog.py", "artifacts/logging/artifactLog.py"):
            tree = ast.parse((source_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = (node.func.attr if isinstance(node.func, ast.Attribute) else
                            node.func.id if isinstance(node.func, ast.Name) else None)
                    self.assertNotIn(name, ("addHandler", "basicConfig", "FileHandler", "StreamHandler",
                                           "open", "commit", "apply", "write_text", "emit_warning"))


if __name__ == "__main__":
    unittest.main()
