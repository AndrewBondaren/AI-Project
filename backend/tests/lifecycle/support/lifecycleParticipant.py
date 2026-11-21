"""Row-like Lifecycle storage in a borrowed mock transaction.

The fixture owns complete indexes. Its caller owns commit/rollback and must
discard staged state on rollback; this participant never publishes a head.
"""
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.application.lifecycle.validation.stateValidator import LifecycleStateValidator
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangesQuery, AcceptedChangeAbsent
from app.dataModel.lifecycle.publication.appendResult import LifecycleAppended
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.dataModel.worldSnapshot.sections.retention import SectionStateRetention, SectionHistoryRetention
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support.acceptedContracts import AcceptedChangeFoundAB, AcceptedChangesResultAB, TransitionAB
from tests.lifecycle.support.snapshotContracts import MockLifecycleSectionRefused


class MockLifecycleParticipant:
    def __init__(self, *, scope: CommitScope, publication: WorldPublicationRef,
                 states: tuple[m.EntityStateA | m.EntityStateB, ...] = (),
                 transitions: tuple[TransitionAB, ...] = ()) -> None:
        self._scope = scope
        self._publication = publication
        self._states = {state.entity: state for state in states}
        self._accepted = {transition.participants[0].after.last_transition: transition for transition in transitions}
        if len(self._states) != len(states) or len(self._accepted) != len(transitions):
            raise ValueError("duplicate initial mock Lifecycle state or accepted transition")
        self._state_validator = LifecycleStateValidator(MockLifecycleSectionRefused)

    def _read(self, publication: WorldPublicationRef, scope: CommitReadScope) -> None:
        scope.assert_active()
        if scope is not self._scope.read_scope or publication != self._publication:
            raise ValueError("mock Lifecycle read is bound to another scope/publication")

    def bind(self, scope: CommitScope) -> "MockLifecycleParticipant":
        scope.assert_active()
        if scope is not self._scope:
            raise ValueError("mock Lifecycle writer is bound to another transaction")
        return self

    async def lookup_accepted_changes(self, request: AcceptedChangesQuery, *, scope: CommitReadScope) -> AcceptedChangesResultAB:
        self._read(request.publication, scope)
        return AcceptedChangesResultAB(publication=request.publication, entries=tuple(
            AcceptedChangeFoundAB(ref=ref, transition=self._accepted[ref])
            if ref in self._accepted else AcceptedChangeAbsent(ref=ref) for ref in request.refs))

    async def read_for_section(self, section: m.LifecycleSectionAB, *, publication: WorldPublicationRef,
                               scope: CommitReadScope) -> tuple[m.CaptureA | m.CaptureB, ...]:
        self._read(publication, scope)
        entities = tuple(p.after.entity for patch in section.patches for p in patch.prepared.transition.participants)
        captures: list[m.CaptureA | m.CaptureB] = []
        for kind in dict.fromkeys(entity.kind for entity in entities):
            if kind == "test_entity_a":
                observations_a: list[m.AbsentA | m.PresentA] = []
                facts_a: list[m.LastTransitionFactA] = []
                for entity in entities:
                    if not isinstance(entity, m.RefA):
                        continue
                    state = self._states.get(entity)
                    if state is None:
                        observations_a.append(m.AbsentA(entity=entity))
                    elif isinstance(state, m.EntityStateA):
                        observations_a.append(m.PresentA(state=state))
                        last = self._accepted.get(state.last_transition)
                        if last is not None:
                            facts_a.append(m.LastTransitionFactA(entity=entity, ref=state.last_transition, operation=last.intent.operation))
                    else:
                        raise TypeError("mock Lifecycle index has a wrong-kind state")
                captures.append(m.CaptureA(publication=publication, entities=tuple(observations_a), last_transitions=tuple(facts_a)))
            else:
                observations_b: list[m.AbsentB | m.PresentB] = []
                facts_b: list[m.LastTransitionFactB] = []
                for entity in entities:
                    if not isinstance(entity, m.RefB):
                        continue
                    state = self._states.get(entity)
                    if state is None:
                        observations_b.append(m.AbsentB(entity=entity))
                    elif isinstance(state, m.EntityStateB):
                        observations_b.append(m.PresentB(state=state))
                        last = self._accepted.get(state.last_transition)
                        if last is not None:
                            facts_b.append(m.LastTransitionFactB(entity=entity, ref=state.last_transition, operation=last.intent.operation))
                    else:
                        raise TypeError("mock Lifecycle index has a wrong-kind state")
                captures.append(m.CaptureB(publication=publication, entities=tuple(observations_b), last_transitions=tuple(facts_b)))
        return tuple(captures)

    async def append(self, section: m.LifecycleSectionAB, *, expected: WorldPublicationRef,
                     target: WorldSnapshotRef) -> LifecycleAppended | MockLifecycleSectionRefused:
        self._scope.assert_active()
        if target.world_uid != expected.world_uid or target.timeline_id != expected.active_timeline_id:
            raise ValueError("assigned target does not belong to the expected world/timeline")
        if expected.active_timeline_id is None:
            raise ValueError("Lifecycle append requires an active timeline")
        query = AcceptedChangesQuery(publication=expected, refs=tuple(
            LifecycleTransitionRef(world_uid=expected.world_uid, origin_timeline_id=expected.active_timeline_id,
                                   change_uid=patch.prepared.transition.intent.change_uid) for patch in section.patches))
        accepted = await self.lookup_accepted_changes(query, scope=self._scope.read_scope)
        captures = await self.read_for_section(section, publication=expected, scope=self._scope.read_scope)
        check = self._state_validator.validate(section, accepted=accepted, captures=captures, expected_world=expected)
        if isinstance(check, MockLifecycleSectionRefused):
            return check
        fresh = tuple(patch for patch, entry in zip(section.patches, accepted.entries, strict=True) if entry.kind == "absent")
        if not fresh:
            return LifecycleAppended(state=None, history=None, changed=())
        # Prepare complete replacements before mutating the borrowed mock store.
        states = dict(self._states)
        transitions = dict(self._accepted)
        for patch in fresh:
            transition = patch.prepared.transition
            transitions[transition.participants[0].after.last_transition] = transition
            for participant in transition.participants:
                states[participant.after.entity] = participant.after
        result = LifecycleAppended(
            state=SectionStateRetention(state=SectionStateRef(snapshot=target, section_key=section.header.key,
                format_version=section.header.format_version), artifacts=()),
            history=SectionHistoryRetention(history=SectionHistoryRef(snapshot=target, section_key=section.header.key,
                format_version=section.header.format_version), artifacts=()),
            changed=tuple(patch.header.ref for patch in fresh))
        self._scope.assert_active()
        self._states, self._accepted = states, transitions
        return result
