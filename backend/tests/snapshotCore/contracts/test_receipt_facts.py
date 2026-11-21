"""Partial admission and caller-specific ordering of shared provenance checks."""
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock
from types import SimpleNamespace

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.application.worldSnapshot.errors import SnapshotReceiptContractError
from app.application.worldSnapshot.service.snapshotMetadataBuilder import SnapshotMetadataBuilder, SnapshotMetadataFailure
from app.application.worldSnapshot.validation.receiptFacts import ReceiptFactsAdmission
from app.application.worldSnapshot.validation.receiptProvenance import collect_receipt_provenance, validate_receipt_provenance
from app.application.worldSnapshot.validation.snapshotReceiptValidator import SnapshotReceiptValidator
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.request.patchSet import PatchSet
from app.application.worldSnapshot.contracts.admittedSectionView import AdmittedSectionView
from tests.snapshotCore.support.fakeSection import HeaderOnlyPatch
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.diagnostics.receiptContract import ReceiptChangedPatchNotInInput
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation
from app.dataModel.worldSnapshot.metadata.metadataIssues import SnapshotMetadataCode as Code
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.dataModel.worldSnapshot.sections.retention import SectionStateRetention, SectionHistoryRetention
from tests.snapshotCore.storage.publication.test_history import KEY, envelope
from tests.snapshotCore.support.fixtures import STAMP
from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService
from app.application.publication.errors import PublicationInfrastructureError


class ReceiptFactsTests(unittest.TestCase):
    def setUp(self):
        self.old = WorldSnapshotRef(world_uid="w", timeline_id="t", snapshot_id="old")
        self.new = self.old.model_copy(update={"snapshot_id": "new"})
        q = WorldPublicationRef(world_uid="w", publication_id="q", snapshot_head=self.old,
            pack_hash="d" * 64, gameplay_started=True, active_timeline_id="t")
        self.bases = {self.old: envelope(self.old)}
        self.patch = PatchRef(operation_id="op", section_key=KEY, ordinal=0)
        self.section = DomainSection[HeaderOnlyPatch](header=SectionHeader(key=KEY, format_version=1, depends_on=()),
            patches=(HeaderOnlyPatch(header=PatchHeader(ref=self.patch, format_version=1, depends_on=(), artifacts=())),))
        self.request = PatchSet[type(self.section)](format_version=1, operation_id="op", preparation_fingerprint="a" * 64,
            world_uid="w", timeline_id="t", turn_id=2, expected_world=q, expected_players=(), sections=(self.section,))
        self.scope = SimpleNamespace(assert_active=lambda: None)
        view = AdmittedSectionView(self.request, self.scope, self.request.sections)
        self.context = SnapshotApplyContext(SnapshotValidationContext("op", q, (), (), self.scope, view),
            self.new, (), None, q.model_copy(update={"publication_id": "next", "snapshot_head": self.new}))

    def test_partial_retention_and_gaps_keep_independent_ref_errors(self):
        foreign = self.new.model_copy(update={"world_uid": "foreign"})
        entry = SectionStateRetention(state=SectionStateRef(snapshot=foreign, section_key=KEY, format_version=1), artifacts=())
        raw = SectionApplyReceipt.model_construct(section_key=KEY, history=(), changed=(self.patch,),
            states=(entry.model_copy(update={"artifacts": "bad"}), object(), entry))
        facts = ReceiptFactsAdmission.admit(raw, section_index=7)
        self.assertEqual([s.index for s in facts.states], [0, 2])
        self.assertIsNone(facts.states[0].retention)
        issues = collect_receipt_provenance(facts, self.context, self.bases)
        self.assertEqual([i.code for i in issues], [Code.UNREACHABLE_STATE] * 2)
        self.assertEqual([i.address[:3] for i in issues], [(7, "states", 0), (7, "states", 2)])
        with self.assertRaises(SnapshotMetadataFailure) as caught:
            SnapshotMetadataBuilder.build(self.context, 2, STAMP, (raw,), self.bases)
        self.assertEqual([i.code for i in caught.exception.diagnostics][-2:], [Code.UNREACHABLE_STATE] * 2)

    def test_input_membership_and_operation_are_independent(self):
        raw = SectionApplyReceipt(section_key=KEY, states=(), history=(),
            changed=(self.patch.model_copy(update={"operation_id": "foreign"}),))
        with self.assertRaises(SnapshotReceiptContractError) as caught:
            SnapshotReceiptValidator().validate(self.section, raw, self.context, self.bases, section_index=2)
        self.assertIsInstance(caught.exception.diagnostics[0], ReceiptChangedPatchNotInInput)
        self.assertEqual(caught.exception.diagnostics[0].section_index, 2)
        self.assertEqual(caught.exception.diagnostics[1].code, Code.FOREIGN_OPERATION)

    def test_invalid_changed_does_not_mean_noop(self):
        state = SectionStateRetention(state=SectionStateRef(snapshot=self.new, section_key=KEY, format_version=1), artifacts=())
        raw = SectionApplyReceipt.model_construct(section_key=KEY, states=(state,), history=(), changed=(object(),))
        facts = ReceiptFactsAdmission.admit(raw, section_index=0)
        self.assertIsNone(facts.changed_empty)
        self.assertNotIn(Code.NOOP_STATE, [i.code for i in collect_receipt_provenance(facts, self.context, self.bases)])
        from pydantic import ValidationError
        with self.assertRaises(SnapshotReceiptContractError) as caught:
            SnapshotReceiptValidator().validate(self.section, raw, self.context, self.bases, section_index=0)
        self.assertIsInstance(caught.exception.__cause__, ValidationError)

    def test_noop_can_have_assigned_history_and_inherit_state(self):
        state = SectionStateRef(snapshot=self.old, section_key=KEY, format_version=1)
        self.bases[self.old] = envelope(self.old, states=(state,))
        raw = SectionApplyReceipt(section_key=KEY, states=(), changed=(), history=(SectionHistoryRetention(
            history=SectionHistoryRef(snapshot=self.new, section_key=KEY, format_version=1), artifacts=()),))
        SnapshotReceiptValidator().validate(self.section, raw, self.context, self.bases, section_index=0)
        result = SnapshotMetadataBuilder.build(self.context, 2, STAMP, (raw,), self.bases)
        self.assertEqual(result[0].history, raw.history)
        self.assertEqual(result[0].states, self.bases[self.old].states)

    def test_wrong_root_and_index_do_not_fabricate_fields(self):
        facts = ReceiptFactsAdmission.admit(object(), section_index=3)
        self.assertEqual(facts.structural_issues[0].address, (3,))
        self.assertEqual(facts.states, ())
        for index, error in ((True, TypeError), (-1, ValueError)):
            with self.assertRaises(error):
                ReceiptFactsAdmission.admit(object(), section_index=index)

    def test_final_history_phase_precedes_state_failure(self):
        state = SectionStateRef(snapshot=self.new, section_key=KEY, format_version=1)
        history = SectionHistoryRef(snapshot=self.new, section_key=KEY, format_version=1)
        raw = SectionApplyReceipt(section_key=KEY, changed=(), states=(SectionStateRetention(state=state, artifacts=()),),
            history=(SectionHistoryRetention(history=history, artifacts=()),))
        with self.assertRaisesRegex(ValueError, "metadata history"):
            validate_receipt_provenance(envelope(self.new, parent=self.old), (raw,), self.bases[self.old], "op")

    def test_interleaved_owners_keep_original_history_order(self):
        player = PlayerSnapshotRef(player_uid="p", snapshot_id="new-player")
        old_player = player.model_copy(update={"snapshot_id": "old-player"})
        validation = replace(self.context.validation, expected_players=(PlayerHeadExpectation(player_uid="p", expected_head=None),))
        context = replace(self.context, validation=validation, player_snapshots=(player,))
        raw = SectionApplyReceipt.model_construct(section_key=KEY, changed=(), states=(), history=(
            SectionHistoryRetention(history=SectionHistoryRef(snapshot=old_player, section_key=KEY, format_version=1), artifacts=()),
            object(),
            SectionHistoryRetention(history=SectionHistoryRef(snapshot=self.old, section_key=KEY, format_version=1), artifacts=()),
        ))
        issues = collect_receipt_provenance(ReceiptFactsAdmission.admit(raw, section_index=4), context, self.bases)
        self.assertEqual([(i.code, i.address) for i in issues], [
            (Code.FOREIGN_HISTORY, (4, "history", 0, "history", "snapshot")),
            (Code.FOREIGN_HISTORY, (4, "history", 2, "history", "snapshot")),
        ])


class ReceiptWiringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fixture = ReceiptFactsTests()
        fixture.setUp()
        self.fixture = fixture
        self.history = SimpleNamespace(read=AsyncMock(), append=AsyncMock())
        from tests.snapshotCore.contracts.test_publication_current_binding import CurrentPublicationTests
        configuration = CurrentPublicationTests()
        configuration.setUp()
        self.registry = SimpleNamespace(diagnostic_types=frozenset(), resolve=lambda section: None)
        self.service = WorldSnapshotService(self.registry, None, None, self.history,
            publication_binding=configuration.binding, operations=SimpleNamespace(
                result_binding=configuration.binding, record_model=configuration.binding.record_model))
        self.scope = fixture.scope
        self.configuration = configuration

    async def test_exact_terminal_replay_has_no_context_or_handler_work(self):
        from app.dataModel.artifacts.lifecycle.operation.claim import PublicationTerminal
        from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
        result = self.configuration.result
        record = self.configuration.binding.record_model(operation_id="op", world_uid="w",
            kind=OperationKind.SNAPSHOT_APPLY, preparation_fingerprint="b" * 64,
            publication_fingerprint="a" * 64, phase=OperationPhase.TERMINAL, fence=1,
            leased_artifacts=(), terminal=result)
        self.service._operations.claim_publication = AsyncMock(return_value=PublicationTerminal[type(result)](record=record))
        self.service._contexts = SimpleNamespace(build=AsyncMock())
        self.service._dependencies = SimpleNamespace(validate=AsyncMock())
        replay = await self.service._claim_publication("op", "w", "b" * 64, "a" * 64)
        self.assertIs(type(replay), type(result))
        self.assertEqual(replay, result)
        self.service._contexts.build.assert_not_called()
        self.service._dependencies.validate.assert_not_called()
        self.history.read.assert_not_awaited()

    async def test_later_validation_refusal_prevents_any_apply(self):
        from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionRefused
        from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
        from app.application.worldSnapshot.service.worldSnapshotService import _SnapshotValidationRefused
        f = self.fixture
        second = f.section.model_copy(update={"header": f.section.header.model_copy(update={"key": "second"}),
            "patches": (HeaderOnlyPatch(header=PatchHeader(ref=PatchRef(operation_id="op", section_key="second", ordinal=0),
                format_version=1, depends_on=(), artifacts=())),)})
        request = f.request.model_copy(update={"sections": (f.section, second)})
        seen = []
        async def accepted(section, context):
            seen.append(context.admitted_sections)
            return SectionAccepted()
        async def refused(section, context):
            seen.append(context.admitted_sections)
            return SectionRefused[type(self.configuration.result.diagnostics[0])](
                category=SnapshotApplyOutcomeKind.REJECTED, diagnostics=self.configuration.result.diagnostics)
        first = SimpleNamespace(validate=AsyncMock(side_effect=accepted), apply=AsyncMock())
        second_handler = SimpleNamespace(validate=AsyncMock(side_effect=refused), apply=AsyncMock())
        self.registry.resolve = lambda section: first if section.header.key == KEY else second_handler
        with self.assertRaises(_SnapshotValidationRefused) as caught:
            await self.service._validate_sections(request, scope=self.scope, resolved_dependencies=())
        self.assertEqual(caught.exception.diagnostics, self.configuration.result.diagnostics)
        self.assertEqual(len(seen), 2)
        self.assertIs(seen[0], seen[1])
        first.apply.assert_not_awaited()
        second_handler.apply.assert_not_awaited()
        self.history.read.assert_not_awaited()

    async def test_base_reuse_is_immutable_and_metadata_does_not_reread(self):
        f = self.fixture
        bases = await self.service._load_pinned_bases(f.context.validation, scope=self.scope, source_bases=f.bases)
        self.history.read.assert_not_awaited()
        with self.assertRaises(TypeError):
            bases[f.old] = f.bases[f.old]
        await self.service._append_metadata(f.context, 2, STAMP, (), bases=bases)
        self.history.read.assert_not_awaited()
        self.history.append.assert_awaited_once()

    async def test_missing_base_stops_before_apply(self):
        self.history.read.return_value = None
        with self.assertRaises(PublicationInfrastructureError) as caught:
            await self.service._load_pinned_bases(self.fixture.context.validation, scope=self.scope, source_bases={})
        self.assertEqual(caught.exception.args[0][0].snapshot, self.fixture.old)
        self.history.append.assert_not_awaited()

    async def test_invalid_receipt_prevents_next_handler_and_cas(self):
        f = self.fixture
        second = f.section.model_copy(update={
            "header": f.section.header.model_copy(update={"key": "second"}),
            "patches": (HeaderOnlyPatch(header=PatchHeader(ref=PatchRef(operation_id="op", section_key="second", ordinal=0),
                format_version=1, depends_on=(), artifacts=())),),
        })
        request = f.request.model_copy(update={"sections": (f.section, second)})
        outcome = SectionApplyReceipt(section_key=KEY, states=(), history=(),
            changed=(f.patch.model_copy(update={"ordinal": 9}),))
        handler = SimpleNamespace(apply=AsyncMock(return_value=outcome))
        next_handler = SimpleNamespace(apply=AsyncMock())
        self.registry.resolve = lambda section: handler if section.header.key == KEY else next_handler
        validation = self.service._contexts.build(request, scope=self.scope, resolved_dependencies=())
        self.service._world = SimpleNamespace(compare_append=AsyncMock())
        scope = SimpleNamespace(read_scope=self.scope)
        with self.assertRaises(SnapshotReceiptContractError):
            async with self.service._apply_to_target(scope, validation,
                    request.sections, f.new, (), bases=f.bases, request=request):
                self.fail("invalid receipt escaped apply boundary")
        handler.apply.assert_awaited_once()
        next_handler.apply.assert_not_awaited()
        self.service._world.compare_append.assert_not_awaited()
