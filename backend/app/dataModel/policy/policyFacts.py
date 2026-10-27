"""Immutable policy observations and their known/waiting/unknown states."""

from enum import Enum
from math import isfinite
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import FactState
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

T_co = TypeVar("T_co", covariant=True)


def _policy_value(value: object) -> None:
    """Facts and predicate values cannot hide mutable data in a frozen record."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and isfinite(value):
        return
    if isinstance(value, Enum):
        _policy_value(value.value)
        return
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            _policy_value(item)
        return
    if isinstance(value, BaseModel) and value.model_config.get("frozen"):
        if value.model_config.get("extra") != "forbid" or value.model_config.get("revalidate_instances") != "always":
            raise ValueError("policy value model requires immutable contract")
        for name in type(value).model_fields:
            _policy_value(getattr(value, name))
        return
    raise ValueError("policy values require immutable finite data")


class KnownFact(BaseModel, Generic[T_co], frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.KNOWN] = FactState.KNOWN
    value: T_co

    @model_validator(mode="after")
    def immutable_value(self):
        _policy_value(self.value)
        return self


class WaitingFact(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.WAITING] = FactState.WAITING
    support_uids: tuple[EntityUid, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_supports(self):
        if len(set(self.support_uids)) != len(self.support_uids):
            raise ValueError("duplicate waiting supports")
        return self


class UnknownFact(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    state: Literal[FactState.UNKNOWN] = FactState.UNKNOWN
    issue: FieldPathError


type FactValue[T] = Annotated[KnownFact[T] | WaitingFact | UnknownFact, Field(discriminator="state")]
