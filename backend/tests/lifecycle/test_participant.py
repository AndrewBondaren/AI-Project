from unittest import IsolatedAsyncioTestCase
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangesQuery
from tests.lifecycle.support.lifecycleParticipant import MockLifecycleParticipant
from tests.lifecycle.support.snapshotContracts import MockLifecycleSectionRefused
from tests.lifecycle.test_apply_predicates import native_and_reads


class MockReadScope(CommitReadScope):
    def __init__(self):
        self.active = True

    def assert_active(self):
        if not self.active:
            raise RuntimeError("expired mock transaction")


class MockCommitScope(CommitScope):
    def __init__(self):
        self._read = MockReadScope()

    @property
    def read_scope(self):
        return self._read

    def assert_active(self):
        self._read.assert_active()


class ParticipantTests(IsolatedAsyncioTestCase):
    async def test_new_mixed_and_noop_append_preserve_original_refs(self):
        native, _, captures, base = native_and_reads()
        target = WorldSnapshotRef(world_uid=base.world_uid, timeline_id=base.active_timeline_id, snapshot_id="assigned")
        for prior in ((), (0, 2), tuple(range(8))):
            states = {fact.state.entity: fact.state for capture in captures for fact in capture.entities if fact.status == "present"}
            for index in prior:
                for participant in native.patches[index].prepared.transition.participants:
                    states[participant.after.entity] = participant.after
            scope = MockCommitScope()
            participant = MockLifecycleParticipant(scope=scope, publication=base, states=tuple(states.values()),
                transitions=tuple(native.patches[i].prepared.transition for i in prior))
            result = await participant.bind(scope).append(native, expected=base, target=target)
            self.assertEqual(result.changed, tuple(p.header.ref for i, p in enumerate(native.patches) if i not in prior))
            if len(prior) == 8:
                self.assertIsNone(result.state)
                self.assertIsNone(result.history)
            else:
                self.assertEqual(result.state.state.snapshot, target)
                self.assertEqual(result.history.history.snapshot, target)
            retry = await participant.append(native, expected=base, target=target)
            self.assertEqual(retry.changed, ())
            self.assertIsNone(retry.state)
            self.assertIsNone(retry.history)
            scope.read_scope.active = False
            with self.assertRaises(RuntimeError):
                await participant.append(native, expected=base, target=target)

    async def test_one_conflict_leaves_every_transition_absent(self):
        native, lookup, captures, base = native_and_reads()
        states = tuple(f.state for c in captures for f in c.entities if f.status == "present")
        # Remove one required present state; the other valid changes must not append.
        scope = MockCommitScope()
        participant = MockLifecycleParticipant(scope=scope, publication=base, states=states[1:])
        target = WorldSnapshotRef(world_uid=base.world_uid, timeline_id=base.active_timeline_id, snapshot_id="assigned")
        result = await participant.append(native, expected=base, target=target)
        self.assertIs(type(result), MockLifecycleSectionRefused)
        accepted = await participant.lookup_accepted_changes(
            AcceptedChangesQuery(publication=base, refs=tuple(e.ref for e in lookup.entries)), scope=scope.read_scope)
        self.assertTrue(all(entry.kind == "absent" for entry in accepted.entries))
        with self.assertRaises(ValueError):
            participant.bind(MockCommitScope())
