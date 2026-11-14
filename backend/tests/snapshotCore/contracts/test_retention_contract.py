"""Native retention and relation diagnostics, without compatibility decoding."""
import unittest

from pydantic import ValidationError

from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.dataModel.worldSnapshot.sections.retention import SectionStateRetention, SectionHistoryRetention
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode, SnapshotApplyRelationIssue
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.encoding.canonicalCodec import encode, decode
from tests.snapshotCore.support.artifactFixtures import descriptor
from tests.snapshotCore.support.diagnostics import diagnostic_roundtrip, target_issue


class RetentionContractTests(unittest.TestCase):
    def test_exact_owner_and_closure_survive_codec_without_flat_fields(self):
        a = descriptor()
        world = WorldSnapshotRef(world_uid="w", timeline_id="t", snapshot_id="s")
        player = PlayerSnapshotRef(player_uid="p", snapshot_id="p-s")
        states = tuple(SectionStateRetention(state=SectionStateRef(snapshot=ref, section_key="s", format_version=1),
                                            artifacts=(a,)) for ref in (world, player))
        history = SectionHistoryRetention(history=SectionHistoryRef(snapshot=world, section_key="s", format_version=1),
                                          artifacts=(a,))
        receipt = SectionApplyReceipt(section_key="s", states=states, history=(history,), changed=())
        self.assertEqual(decode(encode(receipt, SNAPSHOT_CORE_SCHEMA), SectionApplyReceipt, SNAPSHOT_CORE_SCHEMA), receipt)
        self.assertEqual(tuple(type(receipt).model_fields), ("section_key", "states", "history", "changed"))
        with self.assertRaises(ValidationError):
            SectionApplyReceipt.model_validate(dict(section_key="s", state_refs=(), history_refs=(),
                                                    changed=(), retained_artifacts=()), strict=True)
        for bad in (states[0].model_copy(update={"artifacts": (a, a)}),
                    states[0].model_copy(update={"state": history.history}),
                    states[0].model_copy(update={"artifacts": []})):
            with self.assertRaises(ValidationError):
                SectionApplyReceipt.model_validate(receipt.model_copy(update={"states": (bad,)}), strict=True)

    def test_relation_context_and_concrete_field_issue_survive_mixed_round_trip(self):
        for code in SnapshotApplyCode:
            context = dict(section_key="s" if code in (SnapshotApplyCode.SECTION_BINDING_MISMATCH,
                                                       SnapshotApplyCode.DEPENDENCY_MISMATCH) else None,
                           player_uid="p" if code is SnapshotApplyCode.PLAYER_EXPECTATION_MISMATCH else None,
                           artifact=descriptor() if code is SnapshotApplyCode.ARTIFACT_UNAVAILABLE else None)
            issue = SnapshotApplyRelationIssue(code=code, **context)
            field = target_issue("field refused")
            result = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED, operation_id="op",
                                         request_fingerprint="b"*64, committed=None, diagnostics=(field, issue))
            restored = diagnostic_roundtrip(result)
            self.assertEqual(restored, result)
            self.assertIs(type(restored.diagnostics[0]), type(field))
            self.assertIs(type(restored.diagnostics[1]), SnapshotApplyRelationIssue)
            for name, value in context.items():
                invalid = {**context, name: None if value is not None else
                           (descriptor() if name == "artifact" else "foreign")}
                with self.assertRaises(ValidationError):
                    SnapshotApplyRelationIssue(code=code, **invalid)
