"""Domain retry equality without changing native order or publication bytes."""

from pydantic import BaseModel

from app.dataModel.lifecycle.operations.kind import LifecycleOperation


def equivalent_transition(left: BaseModel, right: BaseModel) -> bool:
    if type(left) is not type(right):
        return False
    a, b = left.intent, right.intent
    if type(a) is not type(b) or (a.operation, a.change_uid, a.reason) != (b.operation, b.change_uid, b.reason):
        return False
    if a.operation is LifecycleOperation.REPLACEMENT:
        for side in ("predecessors", "successors"):
            aa, bb = getattr(a, side), getattr(b, side)
            if len(set(aa)) != len(aa) or len(set(bb)) != len(bb) or set(aa) != set(bb):
                return False
        if set(a.predecessors) & set(a.successors) or set(b.predecessors) & set(b.successors):
            return False
    elif a.entity != b.entity:
        return False
    aa = {participant.after.entity: participant for participant in left.participants}
    bb = {participant.after.entity: participant for participant in right.participants}
    if len(aa) != len(left.participants) or len(bb) != len(right.participants):
        return False
    return aa == bb
