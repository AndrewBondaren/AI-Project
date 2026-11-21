"""Structural coherence of a successful prepared result, not storage admission."""

from pydantic import BaseModel

from app.dataModel.lifecycle.operations.kind import LifecycleOperation as Op
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle


def validate_prepared[P: BaseModel](prepared: P) -> P:
    intent = prepared.transition.intent
    participants = prepared.transition.participants
    replacement = intent.operation is Op.REPLACEMENT
    refs = intent.predecessors + intent.successors if replacement else (intent.entity,)
    if len(set(refs)) != len(refs) or len(participants) != len(refs):
        raise ValueError("successful transition must have one participant per distinct intent entity")
    if prepared.base.active_timeline_id is None:
        raise ValueError("successful transition requires a captured timeline")
    for index, (ref, participant) in enumerate(zip(refs, participants, strict=True)):
        if participant.after.entity != ref:
            raise ValueError("participant order/identity must follow the intent")
        before = participant.before
        before_ref = before.state.entity if isinstance(before, PresentLifecycle) else before.entity
        if before_ref != ref:
            raise ValueError("participant before/after identities differ")
        creates = intent.operation is Op.CREATE or (replacement and index >= len(intent.predecessors))
        if creates and not isinstance(before, AbsentLifecycle):
            raise ValueError("successful creation requires an absent before state")
        if not creates:
            if not isinstance(before, PresentLifecycle) or before.state.active is (intent.operation is Op.REACTIVATE):
                raise ValueError("successful transition has an invalid before activity")
        expected_active = creates or intent.operation is Op.REACTIVATE
        if participant.after.active is not expected_active:
            raise ValueError("successful transition has an invalid after activity")
        last = participant.after.last_transition
        if (last.world_uid, last.origin_timeline_id, last.change_uid) != (
            prepared.base.world_uid, prepared.base.active_timeline_id, intent.change_uid
        ):
            raise ValueError("after state must reference this transition and its captured scope")
    return prepared
