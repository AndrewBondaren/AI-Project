"""Explicit registration, exact dispatch and runtime capability declarations (4B1)."""

import ast
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import create_autospec

from pydantic import BaseModel, ValidationError
from app.application.encoding.canonicalCodec import encode as canonical_encode

from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext, SnapshotApplyContext
from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.dataModel.artifacts.references import ArtifactFormatRegistry, ArtifactKind, ArtifactRef
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from tests.snapshotCore.support.fakeSection import (
    FakeTarget, FakeChange, FakePrepared, FakePatch, FakeSection, FakeSectionHandler, FAKE_SECTION_SCHEMA,
)


class SectionRegistryTests(unittest.TestCase):
    @staticmethod
    def _complete(coroutine):
        # These ports/fixtures perform no IO. Any real suspension is a test failure.
        # This also avoids creating Windows asyncio's loopback socketpair in contract tests.
        try:
            coroutine.send(None)
        except StopIteration as result:
            return result.value
        finally:
            coroutine.close()
        raise AssertionError("contract fixture unexpectedly suspended")

    def setUp(self) -> None:
        self.key = RegistryKey[PatchSectionRegistry]("test.section")
        self.manifest = FAKE_SECTION_SCHEMA
        self.contract = SectionContract(key=self.key, section_model=FakeSection,
                                        supported_versions=frozenset({1, 2}), manifest=self.manifest)
        self.handler = FakeSectionHandler(self.contract)
        self.section = FakeSection(header=SectionHeader(key=self.key, format_version=1, depends_on=()),
            patches=(FakePatch(header=PatchHeader(ref=PatchRef(operation_id="op", section_key=self.key, ordinal=0),
                format_version=1, depends_on=(), artifacts=()), target=FakeTarget(name="house"),
                change=FakeChange(amount=3), prepared=FakePrepared(values=(1, 2, 3))),))
        self.read_scope = create_autospec(CommitReadScope, instance=True)
        self.scope = create_autospec(CommitScope, instance=True)
        self.scope.read_scope = self.read_scope
        self.publication = WorldPublicationRef(world_uid="world", publication_id="p", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id="timeline", gameplay_started=True)
        self.context = SnapshotValidationContext(operation_id="op", expected_world=self.publication,
            expected_players=(), resolved_dependencies=(), read_scope=self.read_scope)

    def test_explicit_registration_preserves_subtype_fields_and_dispatches(self) -> None:
        registry = SectionRegistry()
        with self.assertRaises(ValueError):
            registry.resolve(self.section)
        with self.assertRaises(TypeError):
            registry.register(self.contract, object())
        registry.register(self.contract, self.handler)
        self.assertEqual(self.handler.calls, [])  # constructors/registration do not execute domain work
        bound = registry.resolve(self.section)
        encoded = bound.encode(self.section)
        decoded = bound.decode(encoded, 1)
        self.assertIs(type(decoded), FakeSection)
        self.assertEqual(decoded, self.section)
        self.assertEqual(decoded.patches[0].prepared.values, (1, 2, 3))
        self._complete(bound.validate(self.section, self.context))
        snapshot = WorldSnapshotRef(world_uid="world", timeline_id="timeline", snapshot_id="tick")
        target = self.publication.model_copy(update={"publication_id": "q", "snapshot_head": snapshot})
        apply_context = SnapshotApplyContext(validation=self.context, world_snapshot=snapshot,
            player_snapshots=(), scope=self.scope, next_publication=target)
        self.assertIs(apply_context.next_publication, target)
        receipt = self._complete(bound.apply(self.section, apply_context))
        self.assertEqual(receipt.section_key, self.key)
        self.assertEqual(self.handler.calls, ["encode", "decode", "validate", "apply"])
        self.assertEqual(bound.manifest, self.manifest)

    def test_runtime_target_must_match_assigned_snapshot_and_pinned_base(self):
        snapshot = WorldSnapshotRef(world_uid="world", timeline_id="timeline", snapshot_id="tick")
        target = self.publication.model_copy(update={"publication_id": "q", "snapshot_head": snapshot})
        context = SnapshotApplyContext(self.context, snapshot, (), self.scope, target)
        foreign = snapshot.model_copy(update={"world_uid": "another"})
        for changes in ({"publication_id": "p"}, {"snapshot_head": None}, {"pack_hash": "b" * 64},
                        {"active_timeline_id": "another"}, {"world_uid": "another", "snapshot_head": foreign}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(context, next_publication=target.model_copy(update=changes))
        with self.assertRaises(TypeError):
            replace(context, next_publication=snapshot)

    def test_duplicate_wrong_binding_models_keys_and_versions_fail_before_handler(self) -> None:
        registry = SectionRegistry()
        registry.register(self.contract, self.handler)
        with self.assertRaises(ValueError):
            registry.register(self.contract, self.handler)
        other_contract = replace(self.contract, key=RegistryKey[PatchSectionRegistry]("other"))
        with self.assertRaises(ValueError):
            SectionRegistry().register(other_contract, self.handler)
        with self.assertRaises(ValueError):
            registry.register(other_contract, FakeSectionHandler(other_contract))
        invalid_sections = (
            self.section.model_copy(update={"header": self.section.header.model_copy(update={"format_version": 3})}),
            self.section.model_copy(update={"header": self.section.header.model_copy(update={"key": other_contract.key})}),
            self.section.model_copy(update={"patches": []}),
            DomainSection[FakePatch](header=self.section.header, patches=self.section.patches),
        )
        bound = registry.require(self.key)
        for section in invalid_sections:
            with self.subTest(section=section):
                with self.assertRaises((ValueError, TypeError, ValidationError)):
                    registry.resolve(section)
                with self.assertRaises((ValueError, TypeError, ValidationError)):
                    bound.encode(section)
                with self.assertRaises((ValueError, TypeError, ValidationError)):
                    self._complete(bound.validate(section, self.context))
        for version in (0, 3, True, "1"):
            with self.assertRaises(ValueError):
                bound.decode(b"bad", version)
        self.assertEqual(self.handler.calls, [])

    def test_section_contract_requires_concrete_frozen_strict_model_and_manifest(self) -> None:
        for changes in ({"section_model": DomainSection}, {"section_model": FakePrepared},
                        {"section_model": DomainSection[BaseModel]},
                        {"supported_versions": frozenset()}, {"supported_versions": frozenset({True})},
                        {"supported_versions": {1}}, {"manifest": CanonicalSchemaManifest(entries=())}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError, ValidationError)):
                replace(self.contract, **changes)
        with self.assertRaises(FrozenInstanceError):
            self.contract.key = "changed"

    def test_decoded_wrong_model_or_key_is_rejected(self) -> None:
        registry = SectionRegistry()
        registry.register(self.contract, self.handler)
        bound = registry.resolve(self.section)
        wrong = self.section.model_copy(update={"header": self.section.header.model_copy(
            update={"key": RegistryKey[PatchSectionRegistry]("other")})})
        with self.assertRaises(ValueError):
            bound.decode(canonical_encode(wrong, self.manifest), 1)
        self.handler.decode = lambda payload, version: FakePrepared(values=())
        with self.assertRaises(TypeError):
            bound.decode(canonical_encode(self.section, self.manifest), 1)

    def test_runtime_capabilities_are_abstract_opaque_and_read_is_not_write(self) -> None:
        for scope_type in (CommitReadScope, CommitScope):
            with self.assertRaises(TypeError):
                scope_type()
            self.assertNotIn("connection", dir(scope_type))
            self.assertNotIn("commit", dir(scope_type))
            self.assertNotIn("transaction", dir(scope_type))
        self.assertFalse(issubclass(CommitReadScope, CommitScope))
        self.assertFalse(hasattr(self.context, "scope"))
        self.assertFalse(hasattr(self.context, "connection"))
        with self.assertRaises(FrozenInstanceError):
            self.context.operation_id = "other"

    def test_artifact_explicit_binding_and_content_dispatch(self) -> None:
        contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.blob"),
            kind=ArtifactKind.BLOB, supported_versions=frozenset({1}), content_model=bytes,
            encode=lambda content: content, decode=lambda payload, version: payload)
        backend = create_autospec(ArtifactBackend, instance=True)
        backend.contract = contract
        registry = ArtifactFormatRegistryBinding()
        with self.assertRaises(ValueError):
            registry.resolve(contract)
        with self.assertRaises(TypeError):
            registry.register(contract, object())
        registry.register(contract, backend)
        backend.write.assert_not_called()
        backend.verify.assert_not_called()
        self.assertIs(registry.resolve(contract), backend)
        self.assertEqual(registry.encode(contract, b"content"), b"content")
        self.assertEqual(registry.decode(contract, b"content", 1), b"content")
        ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key=contract.key, format_version=1,
                          content_hash="b" * 64, nbytes=7)
        self._complete(registry.verify(ref))
        self._complete(registry.delete(ref))
        backend.verify.assert_awaited_once_with(ref)
        backend.delete.assert_awaited_once_with(ref)
        self.assertEqual(registry.metadata(contract.key).supported_versions, frozenset({1}))

    def test_artifact_registry_rejects_duplicate_wrong_contract_content_and_descriptor(self) -> None:
        contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.blob"),
            kind=ArtifactKind.BLOB, supported_versions=frozenset({1}), content_model=bytes,
            encode=lambda content: content, decode=lambda payload, version: payload)
        backend = create_autospec(ArtifactBackend, instance=True)
        backend.contract = contract
        registry = ArtifactFormatRegistryBinding()
        registry.register(contract, backend)
        with self.assertRaises(ValueError):
            registry.register(contract, backend)
        different = replace(contract)
        with self.assertRaises(TypeError):
            registry.resolve(different)
        with self.assertRaises(ValueError):
            ArtifactFormatRegistryBinding().register(different, backend)
        with self.assertRaises(TypeError):
            registry.encode(contract, FakePrepared(values=()))
        for version in (0, 2, True, "1"):
            with self.assertRaises(ValueError):
                registry.decode(contract, b"data", version)
        for changes in ({"kind": ArtifactKind.SQL_ROWS, "row_count": 1}, {"format_version": 2},
                        {"format_key": RegistryKey[ArtifactFormatRegistry]("unknown")}):
            ref = ArtifactRef.model_validate(dict(kind=ArtifactKind.BLOB, format_key=contract.key,
                format_version=1, content_hash="a" * 64, nbytes=3))
            ref = ref.model_copy(update=changes)
            with self.assertRaises(ValueError):
                self._complete(registry.verify(ref))
        backend.verify.assert_not_called()

    def test_artifact_rowset_model_binding_and_codec_output_validation(self) -> None:
        contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.rows"),
            kind=ArtifactKind.SQL_ROWS, supported_versions=frozenset({1}), content_model=FakePrepared,
            encode=lambda content: content.model_dump_json().encode(),
            decode=lambda payload, version: FakePrepared.model_validate_json(payload),
            row_count=lambda content: len(content.values))
        backend = create_autospec(ArtifactBackend, instance=True)
        backend.contract = contract
        registry = ArtifactFormatRegistryBinding()
        registry.register(contract, backend)
        content = FakePrepared(values=(1, 2))
        self.assertEqual(registry.decode(contract, registry.encode(contract, content), 1), content)
        with self.assertRaises(ValidationError):
            registry.encode(contract, content.model_copy(update={"values": [1, 2]}))
        for changes in ({"content_model": bytes}, {"content_model": BaseModel},
                        {"kind": ArtifactKind.BLOB}, {"supported_versions": frozenset({0})}):
            with self.assertRaises((ValueError, TypeError, ValidationError)):
                replace(contract, **changes)
        invalid_codec = replace(contract, encode=lambda value: "not bytes")
        invalid_backend = create_autospec(ArtifactBackend, instance=True)
        invalid_backend.contract = invalid_codec
        registry = ArtifactFormatRegistryBinding()
        registry.register(invalid_codec, invalid_backend)
        with self.assertRaises(TypeError):
            registry.encode(invalid_codec, content)

    def test_application_ports_have_no_concrete_storage_or_service_imports(self) -> None:
        root = Path(__file__).resolve().parents[3] / "app" / "application"
        for namespace in ("patch", "worldSnapshot", "artifacts", "publication"):
            for source in (root / namespace).rglob("*.py"):
                tree = ast.parse(source.read_text(encoding="utf-8"))
                if source.name == "__init__.py":
                    self.assertEqual(tree.body, [])
                for node in ast.walk(tree):
                    imports = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                               [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for name in imports:
                        emitter = source.relative_to(root).as_posix() in {
                            "worldSnapshot/logging/snapshotLog.py", "artifacts/logging/artifactLog.py",
                        }
                        if emitter and name in ("logging", "app.core.logLevel"):
                            continue
                        self.assertFalse(any(name == prefix or name.startswith(prefix + ".")
                            for prefix in ("app.db", "app.core", "app.storage", "sqlite3", "aiosqlite", "logging")), source)
                        allowed_service_edge = (
                            source.relative_to(root).as_posix() == "artifacts/staging/artifactStaging.py"
                            and name == "app.application.publication.service.operationLedger")
                        builder_edge = (source.relative_to(root).as_posix() == "worldSnapshot/service/worldSnapshotService.py"
                                        and name == "app.application.worldSnapshot.service.snapshotMetadataBuilder")
                        if not (allowed_service_edge or builder_edge):
                            self.assertNotIn(".service.", name, source)

    def test_metadata_builder_merges_pinned_state_and_partitions_tick_receipts(self):
        from app.application.worldSnapshot.service.snapshotMetadataBuilder import SnapshotMetadataBuilder
        from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
        from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation
        from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef
        from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata
        from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef
        from tests.snapshotCore.support.artifactFixtures import descriptor
        from tests.snapshotCore.support.fixtures import STAMP

        parent = WorldSnapshotRef(world_uid="world", timeline_id="timeline", snapshot_id="old")
        world = parent.model_copy(update={"snapshot_id": "tick"})
        player = PlayerSnapshotRef(player_uid="p1", snapshot_id="player")
        expected = self.publication.model_copy(update={"snapshot_head": parent})
        target = expected.model_copy(update={"publication_id": "next", "snapshot_head": world})
        validation = replace(self.context, expected_world=expected,
            expected_players=(PlayerHeadExpectation(player_uid="p1", expected_head=None),))
        ctx = SnapshotApplyContext(validation, world, (player,), self.scope, target)
        old = SectionStateRef(snapshot=parent, section_key=self.key, format_version=1)
        unchanged = old.model_copy(update={"section_key": RegistryKey[PatchSectionRegistry]("unchanged")})
        base = WorldSnapshotMetadata(ref=parent, parent=None, operation_id="prior", turn_id=1,
            created_at=STAMP, envelope_format_version=1, base_pack_hash="a"*64, state_refs=(old, unchanged),
            history_refs=(), retained_artifacts=())
        state = old.model_copy(update={"snapshot": world})
        event = SectionHistoryRef(snapshot=player, section_key=self.key, format_version=1)
        artifact = descriptor()
        receipt = SectionApplyReceipt(section_key=self.key, changed=(self.section.patches[0].header.ref,),
            state_refs=(state,), history_refs=(event,), retained_artifacts=(artifact,))
        def build(receipts, retained, bases):
            return SnapshotMetadataBuilder.build(ctx, 2, STAMP, receipts, bases, retained)

        w, p = build((receipt,), {player: (artifact,)}, {parent: base})
        self.assertEqual((w.ref, w.parent, w.state_refs, w.history_refs, w.retained_artifacts),
                         (world, parent, (state, unchanged), (), ()))
        self.assertEqual((p.ref, p.parent, p.state_refs, p.history_refs, p.retained_artifacts),
                         (player, None, (), (event,), (artifact,)))
        noop, _ = build((), {}, {parent: base})
        self.assertEqual(noop.state_refs, base.state_refs)
        for bad in (receipt.model_copy(update={"changed": ()}),
                    receipt.model_copy(update={"history_refs": (event.model_copy(update={"snapshot": parent}),)}),
                    receipt.model_copy(update={"state_refs": (state.model_copy(update={"snapshot":
                        parent.model_copy(update={"snapshot_id": "unreachable"})}),)})):
            with self.assertRaises(ValueError):
                build((bad,), {player: (artifact,)}, {parent: base})
        with self.assertRaises(ValueError):
            build((receipt,), {}, {parent: base})
        with self.assertRaises(ValueError):
            build((), {}, {})
