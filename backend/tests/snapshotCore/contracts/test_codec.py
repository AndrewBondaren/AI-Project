"""Core canonical v1 golden bytes, binding closure and hostile/old-format inputs."""

from dataclasses import replace
from enum import StrEnum
from hashlib import sha256
import unittest
from unittest.mock import patch, create_autospec

from app.application.encoding.canonicalCodec import (
    CanonicalEncodingError, content_digest, decode, digest, encode, merge_manifests,
)
from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.contracts.sectionHandler import SectionContract, DomainSectionHandler
from app.application.worldData.pack.io.tileCodec import TileCodec, PAYLOAD_KIND_WORLD_MAP
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import SectionHeader, DomainSection
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef, PlayerHeadExpectation
from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError, ReferenceIssueContext, ReferenceIssueReason
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.spatial.facing import Facing
from tests.snapshotCore.support.fakeSection import (
    FakeTarget, FakeChange, FakePrepared, FakePatch, FakeSection, FakeSectionHandler, FAKE_SECTION_SCHEMA,
)


class CanonicalRequestCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = RegistryKey[PatchSectionRegistry]("test.section")
        self.contract = SectionContract(key=self.key, section_model=FakeSection,
            supported_versions=frozenset({1, 2}), manifest=FAKE_SECTION_SCHEMA)
        self.handler = FakeSectionHandler(self.contract)
        self.registry = SectionRegistry()
        self.registry.register(self.contract, self.handler)
        self.codec = PatchSetCodec(self.registry, PatchSet[FakeSection])
        self.publication = WorldPublicationRef(world_uid="w", publication_id="p", pack_hash="a" * 64,
            snapshot_head=None, active_timeline_id="t", gameplay_started=True)
        self.empty = PatchSet[FakeSection](format_version=1, operation_id="o", preparation_fingerprint="b" * 64,
            world_uid="w", timeline_id="t", turn_id=1, expected_world=self.publication, expected_players=(), sections=())
        self.section = FakeSection(header=SectionHeader(key=self.key, format_version=1, depends_on=()), patches=(
            FakePatch(header=PatchHeader(ref=PatchRef(operation_id="o", section_key=self.key, ordinal=0),
                format_version=1, depends_on=(), artifacts=()), target=FakeTarget(name="house"),
                change=FakeChange(amount=3), prepared=FakePrepared(values=(1, 2, 3))),))
        self.request = self.empty.model_copy(update={"sections": (self.section,)})
        self.snapshot = WorldSnapshotMetadata(ref=WorldSnapshotRef(world_uid="w", timeline_id="t", snapshot_id="s"),
            parent=None, operation_id="o", turn_id=1, created_at="2026-10-30T00:00:00.000000Z",
            envelope_format_version=1, base_pack_hash="a" * 64, state_refs=(), history_refs=(), retained_artifacts=())

    def _projection(self, request=None):
        return decode(self.codec.encode(request or self.request), tuple, self.registry.manifest)

    def _changed_projection(self, name, value):
        version, pairs = self._projection()
        return encode((version, tuple((key, value if key == name else item) for key, item in pairs)), self.registry.manifest)

    def test_raw_digest_is_shared_with_canonical_and_tile_hashing(self):
        for payload in (b"", b"abc", bytes(range(256))):
            self.assertEqual(content_digest(payload), sha256(payload).digest())
            self.assertEqual(TileCodec.content_hash(payload), sha256(payload).hexdigest())
        for payload in (bytearray(b"abc"), "abc", True):
            with self.assertRaises(CanonicalEncodingError):
                content_digest(payload)
        with patch("app.application.encoding.canonicalCodec.content_digest", return_value=b"digest") as raw:
            self.assertEqual(digest((1, "x"), PATCH_CORE_SCHEMA), b"digest")
            raw.assert_called_once_with(encode((1, "x"), PATCH_CORE_SCHEMA))
        with patch("app.application.worldData.pack.io.tileCodec.content_digest", return_value=b"digest") as raw:
            self.assertEqual(TileCodec.content_hash(b"blob"), b"digest".hex())
            raw.assert_called_once_with(b"blob")
        tile = TileCodec()
        blob = tile.encode(PAYLOAD_KIND_WORLD_MAP, {"cells": []})
        self.assertEqual(tile.decode(blob), (PAYLOAD_KIND_WORLD_MAP, {"cells": []}))

    def test_core_manifests_have_exact_reserved_ids_and_shared_dependencies(self):
        by_id = {entry.type_id: entry for entry in SNAPSHOT_CORE_SCHEMA.entries}
        self.assertEqual(set(by_id), {110, *range(20001, 20018), *range(20101, 20140)})
        self.assertIs(by_id[20101].python_type, WorldSnapshotRef)
        self.assertIs(by_id[20133].python_type, WorldSnapshotMetadata)
        self.assertIs(by_id[20139].python_type, RuntimeIssueContext)
        self.assertIs(by_id[110].python_type, Facing)
        self.assertNotIn(PatchSet, {entry.python_type for entry in SNAPSHOT_CORE_SCHEMA.entries})
        self.assertNotIn(FakeSection, {entry.python_type for entry in SNAPSHOT_CORE_SCHEMA.entries})
        combined = merge_manifests(ARTIFACT_CORE_SCHEMA, PATCH_CORE_SCHEMA, SNAPSHOT_CORE_SCHEMA)
        self.assertEqual(len(combined.entries), 57)
        self.assertEqual(encode(self.snapshot, combined), encode(self.snapshot, SNAPSHOT_CORE_SCHEMA))
        # Manifest iteration order and Python names are not wire identities.
        reversed_schema = CanonicalSchemaManifest(entries=tuple(reversed(SNAPSHOT_CORE_SCHEMA.entries)))
        self.assertEqual(encode(self.snapshot, reversed_schema), encode(self.snapshot, SNAPSHOT_CORE_SCHEMA))
        original_payload = self.codec.encode(self.request)
        original_name = FakeSection.__name__
        try:
            FakeSection.__name__ = "RenamedPythonClass"
            self.assertEqual(self.codec.encode(self.request), original_payload)
        finally:
            FakeSection.__name__ = original_name

    def test_empty_tick_and_world_player_snapshot_golden_bytes_and_hash(self):
        actual = self.codec.encode(self.empty)
        self.assertEqual(actual, bytes.fromhex(
            "08000000000000031302000000000000000200010800000000000002ff08000000000000002204000000000000000e666f72"
            "6d61745f76657273696f6e020000000000000002000108000000000000001f04000000000000000c6f7065726174696f6e5f"
            "69640400000000000000016f0800000000000000690400000000000000177072657061726174696f6e5f66696e6765727072"
            "696e740400000000000000406262626262626262626262626262626262626262626262626262626262626262626262626262"
            "626262626262626262626262626262626262626262626262626208000000000000001c040000000000000009776f726c645f"
            "7569640400000000000000017708000000000000001e04000000000000000b74696d656c696e655f69640400000000000000"
            "017408000000000000001b0400000000000000077475726e5f69640200000000000000020001080000000000000173040000"
            "00000000000e65787065637465645f776f726c6407000000000000015308000000000000014a020000000000000003004e87"
            "08000000000000013508000000000000001c040000000000000009776f726c645f7569640400000000000000017708000000"
            "000000002104000000000000000e7075626c69636174696f6e5f69640400000000000000017008000000000000005b040000"
            "0000000000097061636b5f686173680400000000000000406161616161616161616161616161616161616161616161616161"
            "616161616161616161616161616161616161616161616161616161616161616161616161616108000000000000001f040000"
            "00000000000d736e617073686f745f6865616400000000000000000008000000000000002504000000000000001261637469"
            "76655f74696d656c696e655f69640400000000000000017408000000000000002304000000000000001067616d65706c6179"
            "5f737461727465640100000000000000010108000000000000002204000000000000001065787065637465645f706c617965"
            "727308000000000000000008000000000000001a04000000000000000873656374696f6e73080000000000000000"
        ))
        self.assertEqual(content_digest(actual).hex(), "65ef2ac1fa4319a3a31ae95515c911ec7998333513c7cd7ecaac1508a4086e1a")
        actual = SnapshotEnvelopeCodec().encode(self.snapshot)
        self.assertEqual(actual, bytes.fromhex(
            "0700000000000002d20800000000000002c9020000000000000003004ea50800000000000002b40800000000000000e80400"
            "000000000000037265660700000000000000d30800000000000000ca020000000000000003004e850800000000000000b508"
            "00000000000000390400000000000000046b696e6406000000000000002308000000000000001a020000000000000003004e"
            "21040000000000000005776f726c6408000000000000001c040000000000000009776f726c645f7569640400000000000000"
            "017708000000000000001e04000000000000000b74696d656c696e655f69640400000000000000017408000000000000001e"
            "04000000000000000b736e617073686f745f6964040000000000000001730800000000000000180400000000000000067061"
            "72656e7400000000000000000008000000000000001f04000000000000000c6f7065726174696f6e5f696404000000000000"
            "00016f08000000000000001b0400000000000000077475726e5f696402000000000000000200010800000000000000370400"
            "0000000000000a637265617465645f617404000000000000001b323032362d31302d33305430303a30303a30302e30303030"
            "30305a08000000000000002b040000000000000017656e76656c6f70655f666f726d61745f76657273696f6e020000000000"
            "000002000108000000000000006004000000000000000e626173655f7061636b5f6861736804000000000000004061616161"
            "6161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161616161"
            "6161616161616161616108000000000000001c04000000000000000a73746174655f72656673080000000000000000080000"
            "00000000001e04000000000000000c686973746f72795f726566730800000000000000000800000000000000240400000000"
            "0000001272657461696e65645f617274696661637473080000000000000000"
        ))
        self.assertEqual(content_digest(actual).hex(), "7e37a16d6e7e8d2db7fe5effe448982184b0288421a7e8039fead2fa71dcf7b1")
        self.assertEqual(self.codec.decode(self.codec.encode(self.empty)), self.empty)
        snapshot_codec = SnapshotEnvelopeCodec()
        for envelope in (self.snapshot, PlayerSnapshotMetadata(
            ref=PlayerSnapshotRef(player_uid="player", snapshot_id="ps"), parent=None, operation_id="o", turn_id=1,
            created_at=self.snapshot.created_at, envelope_format_version=1, state_refs=(), history_refs=(), retained_artifacts=())):
            encoded = snapshot_codec.encode(envelope)
            self.assertEqual(snapshot_codec.decode(encoded), envelope)
            self.assertEqual(snapshot_codec.encode(snapshot_codec.decode(encoded)), encoded)

    def test_concrete_section_roundtrip_and_request_binding_covers_each_input(self):
        payload = self.codec.encode(self.request)
        self.assertEqual(self.codec.decode(payload), self.request)
        self.assertEqual(self.codec.fingerprint(self.request), content_digest(payload).hex())
        self.assertEqual(self.codec.fingerprint_bytes(payload), self.codec.fingerprint(self.request))
        for changes in ({"operation_id": "other"}, {"preparation_fingerprint": "c" * 64},
                        {"world_uid": "other", "expected_world": self.publication.model_copy(update={"world_uid": "other"})},
                        {"timeline_id": "branch"}, {"turn_id": 2},
                        {"expected_world": self.publication.model_copy(update={"publication_id": "other"})},
                        {"expected_players": (PlayerHeadExpectation(player_uid="player", expected_head=None),)},
                        {"sections": ()},
                        {"sections": (self.section.model_copy(update={"patches": (
                            self.section.patches[0].model_copy(update={"change": FakeChange(amount=4)}),)}),)}):
            with self.subTest(changes=changes):
                changed = self.request.model_copy(update=changes)
                self.assertNotEqual(self.codec.fingerprint(changed), self.codec.fingerprint(self.request))

    def test_declared_section_order_is_preserved_and_part_of_fingerprint(self):
        class OtherSection(DomainSection[FakePatch]):
            pass
        manifest = merge_manifests(FAKE_SECTION_SCHEMA, CanonicalSchemaManifest(entries=(
            RegisteredTypeEntry(type_id=90006, python_type=OtherSection, kind=CanonicalTypeKind.RECORD),)))
        other_key = RegistryKey[PatchSectionRegistry]("a.other")
        contract = SectionContract(key=other_key, section_model=OtherSection,
            supported_versions=frozenset({1}), manifest=manifest)
        handler = create_autospec(DomainSectionHandler, instance=True)
        handler.contract = contract
        handler.encode.side_effect = lambda section: encode(section, manifest)
        handler.decode.side_effect = lambda payload, version: decode(payload, OtherSection, manifest)
        self.registry.register(contract, handler)
        other = OtherSection(header=SectionHeader(key=other_key, format_version=1, depends_on=()),
            patches=(self.section.patches[0],))
        codec = PatchSetCodec(self.registry, PatchSet[FakeSection | OtherSection])
        request = PatchSet[FakeSection | OtherSection].model_validate(
            {**self.empty.model_dump(), "sections": (self.section, other)})
        self.assertEqual(tuple(section.header.key for section in codec.decode(codec.encode(request)).sections),
                         (self.key, other_key))
        self.assertNotEqual(codec.fingerprint(request), codec.fingerprint(request.model_copy(
            update={"sections": tuple(reversed(request.sections))})))

    def test_projection_uses_model_declaration_and_canonical_player_order(self):
        a = PlayerHeadExpectation(player_uid="a", expected_head=None)
        z = PlayerHeadExpectation(player_uid="z", expected_head=None)
        request = self.request.model_copy(update={"expected_players": (z, a)})
        version, pairs = self._projection(request)
        self.assertEqual(tuple(key for key, value in pairs), tuple(type(request).model_fields))
        self.assertEqual(version, request.format_version)
        self.assertEqual(self.codec.decode(self.codec.encode(request)).expected_players, (a, z))
        self.assertEqual(self.codec.fingerprint(request), self.codec.fingerprint(request.model_copy(update={"expected_players": (a, z)})))
        with self.assertRaises(CanonicalEncodingError):
            self.codec.decode(self._changed_projection("expected_players", (z, a)))

    def test_bad_projection_shapes_fields_order_and_unknown_formats_are_rejected(self):
        version, pairs = self._projection()
        for projection in ((0, pairs), (2, pairs), (True, pairs), (1, pairs[:-1]), (1, pairs + (pairs[0],)),
                           (1, tuple(reversed(pairs))), (1, pairs + (("extra", 1),)), (1, ("bad",)), ()):
            with self.subTest(projection=projection), self.assertRaises((ValueError, TypeError)):
                self.codec.decode(encode(projection, self.registry.manifest))
        for field, value in (("format_version", True), ("format_version", 2), ("turn_id", True), ("sections", 1)):
            with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                self.codec.decode(self._changed_projection(field, value))
        for encoded in (b"", self.codec.encode(self.request)[:-1], self.codec.encode(self.request) + b"trailing"):
            with self.assertRaises(CanonicalEncodingError):
                self.codec.decode(encoded)
        with self.assertRaises(CanonicalEncodingError):
            self.codec.encode(self.request.model_copy(update={"format_version": 2}))

    def test_section_key_version_noncanonical_and_unknown_types_refuse_without_domain_work(self):
        section_bytes = self.registry.resolve(self.section).encode(self.section)
        bad_sections = (
            (("unknown", 1, section_bytes),), ((self.key, 3, section_bytes),),
            ((self.key, True, section_bytes),), ((self.key, 1, b"not canonical"),),
            ((self.key, 1, section_bytes), (self.key, 1, section_bytes)),
            ((self.key, 2, section_bytes),), ((self.key, 1, section_bytes + b"extra"),),
            ((self.key, 1, encode(1, PATCH_CORE_SCHEMA)),),
        )
        encoded_cases = [self._changed_projection("sections", sections) for sections in bad_sections]
        for encoded in encoded_cases:
            self.handler.calls.clear()
            with self.subTest(encoded=encoded), self.assertRaises((ValueError, TypeError)):
                self.codec.decode(encoded)
            self.assertNotIn("apply", self.handler.calls)
            self.assertNotIn("validate", self.handler.calls)
            self.assertTrue(all(call == "decode" for call in self.handler.calls))

    def test_registered_manifest_collision_fails_without_codec_calls_or_registration(self):
        for entry in (
            RegisteredTypeEntry(type_id=20101, python_type=FakePrepared, kind=CanonicalTypeKind.RECORD),
            RegisteredTypeEntry(type_id=99991, python_type=WorldSnapshotRef, kind=CanonicalTypeKind.RECORD),
        ):
            manifest = CanonicalSchemaManifest(entries=(
                RegisteredTypeEntry(type_id=90001, python_type=FakeSection, kind=CanonicalTypeKind.RECORD), entry))
            contract = replace(self.contract, manifest=manifest)
            handler = FakeSectionHandler(contract)
            registry = SectionRegistry()
            with self.assertRaises(CanonicalEncodingError):
                registry.register(contract, handler)
            self.assertEqual(handler.calls, [])
            with self.assertRaises(ValueError):
                registry.require(contract.key)

    def test_read_upgrade_does_not_change_original_request_fingerprint(self):
        class OldSection(DomainSection[FakePatch]):
            legacy_note: str
        # A frozen historical schema has a different field declaration under
        # the same versioned domain type identity. Core sees only opaque bytes.
        old_schema = CanonicalSchemaManifest(entries=tuple(
            entry.model_copy(update={"python_type": OldSection}) if entry.python_type is FakeSection else entry
            for entry in FAKE_SECTION_SCHEMA.entries))
        old_section = OldSection(header=self.section.header, patches=self.section.patches, legacy_note="v1")
        old_bytes = encode(old_section, old_schema)
        original = self._changed_projection("sections", ((self.key, 1, old_bytes),))
        def read_upgrade(payload, version):
            if version == 1:
                legacy = decode(payload, OldSection, old_schema)
                return FakeSection(header=legacy.header.model_copy(update={"format_version": 2}), patches=legacy.patches)
            return decode(payload, FakeSection, self.contract.manifest)
        self.handler.decode = read_upgrade
        upgraded = self.codec.decode(original)
        self.assertEqual(upgraded.sections[0].header.format_version, 2)
        self.assertEqual(self.codec.fingerprint_bytes(original), content_digest(original).hex())
        self.assertNotEqual(self.codec.fingerprint(upgraded), self.codec.fingerprint_bytes(original))
        self.assertEqual(self.codec.decode(self.codec.encode(upgraded)), upgraded)
        # A historical decoder still rejects noncanonical fields before upgrade.
        identity, pairs = decode(old_bytes[9:], tuple, old_schema)
        malformed_body = encode((identity, tuple(reversed(pairs))), old_schema)
        malformed = bytes([7]) + len(malformed_body).to_bytes(8, "big") + malformed_body
        with self.assertRaises(CanonicalEncodingError):
            self.codec.decode(self._changed_projection("sections", ((self.key, 1, malformed),)))

    def test_snapshot_rejects_unknown_format_wrong_record_and_corrupt_refs(self):
        codec = SnapshotEnvelopeCodec()
        for payload in (encode(self.publication, SNAPSHOT_CORE_SCHEMA), codec.encode(self.snapshot) + b"x",
                        encode(self.snapshot.model_copy(update={"envelope_format_version": 2}), SNAPSHOT_CORE_SCHEMA)):
            with self.assertRaises(CanonicalEncodingError):
                codec.decode(payload)
        with self.assertRaises(CanonicalEncodingError):
            codec.encode(self.snapshot.model_copy(update={"envelope_format_version": 2}))
        with self.assertRaises((ValueError, TypeError)):
            codec.encode(self.snapshot.model_copy(update={"ref": self.snapshot.ref.model_copy(update={"world_uid": ""})}))

    def test_shared_diagnostics_roundtrip_and_runtime_enum_requires_explicit_owner(self):
        runtime = RuntimeIssueContext(world_uid="w", snapshot_uid=None, content_revision=None, source_uid=None,
            body_uids=(), cell=None, face=next(iter(Facing)),
            fallback_action=ReferenceIssueReason.DEFAULT_APPLIED, fallback_reason=ReferenceIssueReason.UNKNOWN_TEMPLATE)
        diagnostic = FieldPathError(path=("target", 1), message="refused",
            reference=ReferenceIssueContext(reason=ReferenceIssueReason.UNKNOWN_TEMPLATE, domain="test"), runtime_context=runtime)
        result = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED, operation_id="o",
            request_fingerprint="a" * 64, committed=None, diagnostics=(diagnostic,))
        self.assertEqual(decode(encode(result, SNAPSHOT_CORE_SCHEMA), SnapshotApplyResult, SNAPSHOT_CORE_SCHEMA), result)
        class DomainReason(StrEnum):
            MISSING = "missing"
        unknown = replace(runtime, fallback_reason=DomainReason.MISSING)
        with self.assertRaises(CanonicalEncodingError):
            encode(unknown, SNAPSHOT_CORE_SCHEMA)
        explicit = merge_manifests(SNAPSHOT_CORE_SCHEMA, CanonicalSchemaManifest(entries=(
            RegisteredTypeEntry(type_id=99999, python_type=DomainReason, kind=CanonicalTypeKind.ENUM),)))
        self.assertEqual(decode(encode(unknown, explicit), RuntimeIssueContext, explicit), unknown)
