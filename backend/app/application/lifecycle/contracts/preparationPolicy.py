"""Declarative reason association; never invokes subject behavior."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.application.lifecycle.contracts.preparationBinding import require_named_model


@dataclass(frozen=True, slots=True)
class LifecycleReasonDeclaration:
    reason_id: str
    reason_model: type[BaseModel]
    entity_kind: str
    owner: str

    def __post_init__(self) -> None:
        require_named_model(self.reason_model)
        if not self.reason_id or not self.entity_kind or not self.owner:
            raise ValueError("reason declarations require identity, entity kind and owner")


@dataclass(frozen=True, slots=True)
class LifecyclePreparationPolicy:
    reasons: tuple[LifecycleReasonDeclaration, ...]
    reactivation_after: frozenset[LifecycleOperation]

    def __post_init__(self) -> None:
        if type(self.reasons) is not tuple or type(self.reactivation_after) is not frozenset:
            raise TypeError("policy must be immutable")
        if not self.reasons or len({r.reason_id for r in self.reasons}) != len(self.reasons):
            raise ValueError("reason identifiers must be nonempty and unique")
        if len({r.reason_model for r in self.reasons}) != len(self.reasons):
            raise ValueError("reason types must be unique")
        if any(type(op) is not LifecycleOperation for op in self.reactivation_after):
            raise TypeError("reactivation policy requires typed operation facts")
