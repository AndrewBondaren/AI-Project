"""History provenance and projection regressions; no domain payload handlers."""

import unittest
from dataclasses import asdict, FrozenInstanceError
from unittest.mock import AsyncMock, patch

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec
from app.application.worldSnapshot.validation.receiptProvenance import validate_receipt_provenance
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult, SnapshotCommitRefs
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.db.repositories.sqlite.snapshotCore.history.rowProjection import encode_history_row, decode_history_row
from tests.snapshotCore.support.fixtures import STAMP, live_database, live_started, run_async

KEY = RegistryKey[PatchSectionRegistry]("test.state")
OTHER = RegistryKey[PatchSectionRegistry]("test.other")


def envelope(ref, *, parent=None, operation="op", states=(), histories=()):
    model = WorldSnapshotMetadata if isinstance(ref, WorldSnapshotRef) else PlayerSnapshotMetadata
    values = dict(ref=ref, parent=parent, operation_id=operation, turn_id=1 if parent is None else 2,
        created_at=STAMP, envelope_format_version=1, state_refs=states, history_refs=histories, retained_artifacts=())
    if isinstance(ref, WorldSnapshotRef):
        values["base_pack_hash"] = "d" * 64
    return model.model_validate(values, strict=True)


def receipt(*, states=(), histories=(), key=KEY, changed=()):
    return SectionApplyReceipt(section_key=key, state_refs=states, history_refs=histories,
        changed=changed, retained_artifacts=())


class SnapshotHistoryTests(unittest.TestCase):
    def test_append_loads_pinned_base_and_receipt_cannot_authorize_an_unknown_old_state(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                _, commits, world, _, history, operations = bundle
                await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "op", "w1", "a" * 64, "b" * 64)
                old = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="old")
                state = SectionStateRef(snapshot=old, section_key=KEY, format_version=1)
                base = envelope(old, states=(state,))
                publication = WorldPublicationRef(world_uid="w1", publication_id="old-publication", pack_hash="d" * 64,
                    snapshot_head=old, active_timeline_id="t1", gameplay_started=True)
                async with commits.transaction("op") as scope:
                    await history.append(scope, base, (receipt(states=(state,)),))
                    await world.compare_append(scope, expected, publication)
                    await operations.record_terminal(scope, SnapshotApplyResult(operation_id="op", request_fingerprint="b" * 64,
                        category=SnapshotApplyOutcomeKind.COMMITTED, diagnostics=(),
                        committed=SnapshotCommitRefs(world_snapshot=old, player_snapshots=(), publication=publication)))
                await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "next", "w1", "a" * 64, "b" * 64)
                new = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="next")
                valid = envelope(new, parent=old, operation="next", states=(state,))
                unknown = state.model_copy(update={"format_version": 2})
                invalid = valid.model_copy(update={"state_refs": (unknown,)})
                async with commits.transaction("next") as scope:
                    with patch.object(history._access, "insert", new_callable=AsyncMock) as insert:
                        with self.assertRaises(ValueError):
                            await history.append(scope, invalid, (receipt(states=(unknown,)),))
                        insert.assert_not_awaited()
                    await history.append(scope, valid, ())
                    self.assertEqual(await history.read(new, scope=scope.read_scope), valid)
        run_async(check())

    def test_multi_participant_receipts_round_trip_through_real_history_rows(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, "op", "w1", "a" * 64, "b" * 64)
                refs = (WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="world"),
                        PlayerSnapshotRef(player_uid="p1", snapshot_id="player"))
                states = tuple(SectionStateRef(snapshot=ref, section_key=KEY, format_version=1) for ref in refs)
                histories = tuple(SectionHistoryRef(snapshot=ref, section_key=KEY, format_version=1) for ref in refs)
                receipts = (receipt(states=states, histories=histories),)
                snapshots = tuple(envelope(ref, states=(state,), histories=(history,))
                                  for ref, state, history in zip(refs, states, histories))
                before = tuple(value.model_dump_json() for value in (*snapshots, *receipts))
                async with bundle[1].transaction("op") as scope:
                    for metadata in snapshots:
                        await bundle[4].append(scope, metadata, receipts)
                        self.assertEqual(await bundle[4].read(metadata.ref, scope=scope.read_scope), metadata)
                for metadata in snapshots:
                    self.assertEqual(await bundle[4].read(metadata.ref), metadata)
                    self.assertEqual(type(metadata).model_validate_json(metadata.model_dump_json()), metadata)
                self.assertEqual(before, tuple(value.model_dump_json() for value in (*snapshots, *receipts)))
        run_async(check())

    def test_old_state_survives_with_new_history_only_from_exact_pinned_base(self):
        for old, new in ((WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="old"),
                          WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="new")),
                         (PlayerSnapshotRef(player_uid="p1", snapshot_id="old"),
                          PlayerSnapshotRef(player_uid="p1", snapshot_id="new"))):
            state = SectionStateRef(snapshot=old, section_key=KEY, format_version=1)
            base = envelope(old, operation="previous", states=(state,))
            history = SectionHistoryRef(snapshot=new, section_key=KEY, format_version=1)
            metadata = envelope(new, parent=old, states=(state,), histories=(history,))
            receipts = (receipt(states=(state,), histories=(history,)),)
            validate_receipt_provenance(metadata, receipts, base, "op")
            # Unchanged section state also survives a legal empty tick.
            validate_receipt_provenance(envelope(new, parent=old, states=(state,)), (), base, "op")
            for wrong_base in (None, envelope(old, operation="previous"), envelope(new)):
                with self.subTest(old=old, base=wrong_base), self.assertRaises(ValueError):
                    validate_receipt_provenance(metadata, receipts, wrong_base, "op")

    def test_receipt_must_match_section_version_assigned_snapshot_and_operation(self):
        world = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="new")
        player = PlayerSnapshotRef(player_uid="p1", snapshot_id="new")
        for ref in (world, player):
            state = SectionStateRef(snapshot=ref, section_key=KEY, format_version=1)
            metadata = envelope(ref, states=(state,))
            others = (world.model_copy(update={"world_uid": "w2"}),
                      player.model_copy(update={"player_uid": "p2"}),
                      ref.model_copy(update={"snapshot_id": "other"}),
                      player if isinstance(ref, WorldSnapshotRef) else world)
            cases = [(receipt(states=(state.model_copy(update={"snapshot": other}),)),) for other in others]
            cases += [(receipt(states=(state.model_copy(update={"section_key": OTHER}),), key=OTHER),),
                      (receipt(states=(state.model_copy(update={"format_version": 2}),)),),
                      (receipt(states=(state,)), receipt()),
                      (receipt(states=(state,), changed=(PatchRef(operation_id="other", section_key=KEY, ordinal=0),)),)]
            for receipts in cases:
                with self.subTest(ref=ref, receipts=receipts), self.assertRaises(ValueError):
                    validate_receipt_provenance(metadata, receipts, None, "op")
            with self.assertRaises(ValueError):
                validate_receipt_provenance(metadata, (receipt(states=(state,)),), None, "other")
            # A receipt cannot silently add state absent from the resulting envelope.
            with self.assertRaises(ValueError):
                validate_receipt_provenance(envelope(ref), (receipt(states=(state,)),), None, "op")
            history = SectionHistoryRef(snapshot=ref, section_key=KEY, format_version=1)
            with self.assertRaises(ValueError):
                validate_receipt_provenance(envelope(ref, histories=(history,)), (), None, "op")
            with self.assertRaises(ValueError):
                validate_receipt_provenance(envelope(ref), (receipt(histories=(history.model_copy(
                    update={"snapshot": ref.model_copy(update={"snapshot_id": "wrong"})}),)),), None, "op")

    def test_policy_strictly_revalidates_copied_and_constructed_inputs(self):
        ref = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="new")
        metadata = envelope(ref)
        for invalid in (metadata.model_copy(update={"turn_id": True}),
                        metadata.model_copy(update={"state_refs": []}),
                        metadata.model_copy(update={"ref": ref.model_copy(update={"world_uid": " bad "})})):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_receipt_provenance(invalid, (), None, "op")
        for invalid in ([receipt()], (receipt().model_copy(update={"state_refs": []}),),
                        (receipt().model_copy(update={"section_key": 123}),)):
            with self.subTest(receipts=invalid), self.assertRaises(ValueError):
                validate_receipt_provenance(metadata, invalid, None, "op")
        base = envelope(ref)
        new = envelope(ref.model_copy(update={"snapshot_id": "next"}), parent=ref)
        with self.assertRaises(ValueError):
            validate_receipt_provenance(new, (), base.model_copy(update={"turn_id": "1"}), "op")
        with self.assertRaises(ValueError):
            validate_receipt_provenance(metadata, (), None, " op ")

    def test_pure_row_projection_round_trip_and_strict_column_body_checks(self):
        codec = SnapshotEnvelopeCodec()
        world = envelope(WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="world"))
        player = envelope(PlayerSnapshotRef(player_uid="p1", snapshot_id="player"))
        for metadata in (world, player):
            row = encode_history_row(metadata, world, codec)
            values = asdict(row)
            self.assertEqual(decode_history_row(values, metadata.ref, codec), metadata)
            with self.assertRaises(FrozenInstanceError):
                row.turn_id = 8
            key = "snapshot_id" if isinstance(metadata, WorldSnapshotMetadata) else "player_snapshot_id"
            for column, bad in ((key, "other"), ("turn_id", True), ("turn_id", "1"), ("turn_id", 1.5),
                                ("created_at", "today"), ("envelope_format_version", 2),
                                ("operation_id", "other"), ("snapshot_data", "text"),
                                ("snapshot_checksum", "f" * 64)):
                with self.subTest(metadata=metadata, column=column), self.assertRaises((ValueError, TypeError, PublicationInfrastructureError)):
                    decode_history_row({**values, column: bad}, metadata.ref, codec)
        with self.assertRaises(ValueError):
            encode_history_row(player, None, codec)
        for invalid in (world.model_copy(update={"operation_id": "other"}), world.model_copy(update={"turn_id": 2})):
            with self.assertRaises(ValueError):
                encode_history_row(player, invalid, codec)

    def test_current_state_without_receipt_is_rejected_before_insert(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                for ref in (WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="new-world"),
                            PlayerSnapshotRef(player_uid="p1", snapshot_id="new-player")):
                    model = WorldSnapshotMetadata if isinstance(ref, WorldSnapshotRef) else PlayerSnapshotMetadata
                    values = dict(ref=ref, parent=None, operation_id="validate", turn_id=1,
                        created_at=STAMP, envelope_format_version=1, history_refs=(), retained_artifacts=(),
                        state_refs=(SectionStateRef(snapshot=ref,
                            section_key=RegistryKey[PatchSectionRegistry]("test.unbacked"), format_version=1),))
                    if isinstance(ref, WorldSnapshotRef):
                        values["base_pack_hash"] = "d" * 64
                    metadata = model.model_validate(values, strict=True)
                    with self.subTest(ref=ref), patch.object(bundle[4]._access, "insert", new_callable=AsyncMock) as insert:
                        async with bundle[1].transaction("validate") as scope:
                            with self.assertRaises(ValueError):
                                await bundle[4].append(scope, metadata, ())
                            insert.assert_not_awaited()
        run_async(check())
