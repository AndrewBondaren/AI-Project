"""Domain retry equality without changing native order or publication bytes."""

from pydantic import BaseModel

from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.application.lifecycle.contracts.typedViews import transition_view


def equivalent_transition(left: BaseModel, right: BaseModel) -> bool:
    if type(left) is not type(right):
        return False
    left_view, right_view = transition_view(left), transition_view(right)
    a, b = left_view.intent, right_view.intent
    if type(a) is not type(b) or (a.operation, a.change_uid, a.reason) != (b.operation, b.change_uid, b.reason):
        return False
    if a.operation is LifecycleOperation.REPLACEMENT and b.operation is LifecycleOperation.REPLACEMENT:
        for aa, bb in ((a.predecessors, b.predecessors), (a.successors, b.successors)):
            if len(set(aa)) != len(aa) or len(set(bb)) != len(bb) or set(aa) != set(bb):
                return False
        if set(a.predecessors) & set(a.successors) or set(b.predecessors) & set(b.successors):
            return False
    elif a.operation is LifecycleOperation.REPLACEMENT or b.operation is LifecycleOperation.REPLACEMENT:
        return False
    elif a.entity != b.entity:
        return False
    left_participants = {participant.after.entity: participant for participant in left_view.participants}
    right_participants = {participant.after.entity: participant for participant in right_view.participants}
    if len(left_participants) != len(left_view.participants) or len(right_participants) != len(right_view.participants):
        return False
    return left_participants == right_participants
