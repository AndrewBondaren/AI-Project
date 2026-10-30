"""Core 4A1: identity/representation validation, immutability and boundaries."""

import ast
import unittest
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.dataModel.artifacts.references import (
    ArtifactFormatMetadata, ArtifactFormatRegistry, ArtifactKind, ArtifactRef,
)
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata, PatchSectionRegistry
from app.dataModel.patch.values import FormatVersion, PatchOrdinal
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import (
    PlayerSnapshotRef, SnapshotChainKind, SnapshotRef, WorldSnapshotRef,
)
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


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


if __name__ == "__main__":
    unittest.main()
