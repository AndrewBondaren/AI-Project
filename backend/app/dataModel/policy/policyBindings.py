"""Frozen request bindings; support observations are supplied by the caller."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import PolicySupportState
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

M = TypeVar("M", bound=BaseModel)
type SourcePath = tuple[str | int, ...]


class PolicySourceBinding(Protocol):
    @property
    def model(self) -> type[BaseModel]: ...

    @property
    def instance(self) -> BaseModel: ...

    @property
    def path(self) -> SourcePath: ...


@dataclass(frozen=True)
class PolicySource(Generic[M]):
    model: type[M]
    instance: M
    path: SourcePath

    def __post_init__(self) -> None:
        if type(self.instance) is not self.model:
            raise ValueError("policy source model/instance mismatch")
        config = self.model.model_config
        if not config.get("frozen") or config.get("extra") != "forbid" or config.get("revalidate_instances") != "always":
            raise ValueError("policy source requires frozen, extra-forbid, revalidated POJO")
        if not isinstance(self.path, tuple) or any(type(p) not in (str, int) for p in self.path):
            raise ValueError("policy source requires immutable field path")


@dataclass(frozen=True)
class PolicyInputs:
    models: tuple[PolicySourceBinding, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.models, tuple) or any(not isinstance(m, PolicySource) for m in self.models):
            raise ValueError("policy inputs require typed source bindings")
        if len({m.model for m in self.models}) != len(self.models):
            raise ValueError("ambiguous policy source model")


class PolicySupportFact(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    uid: EntityUid
    state: PolicySupportState
    issues: tuple[FieldPathError, ...] = ()


@dataclass(frozen=True)
class PolicyFacts(PolicyInputs):
    supports: tuple[PolicySupportFact, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.supports, tuple) or any(not isinstance(s, PolicySupportFact) for s in self.supports):
            raise ValueError("policy facts require typed support observations")
        if len({s.uid for s in self.supports}) != len(self.supports):
            raise ValueError("duplicate policy support observation")
