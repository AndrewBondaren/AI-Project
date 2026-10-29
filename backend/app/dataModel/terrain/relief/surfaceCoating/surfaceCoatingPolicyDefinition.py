"""Terrain declares the rock-cliff prohibition; the common compiler/resolver executes it."""
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.policy.declarations.fieldPolicy import SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.declarations.policyDeclaration import PolicyOwner, ValuePolicy
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyIssueReason, PolicyStage
from app.dataModel.policy.policyFacts import FactValue
from app.dataModel.policy.policyReferences import FactValueRef
from app.dataModel.policy.policyRules import DisableEffect, Equal, IsPresent, PolicyFallback, SelectBehaviorEffect
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import (
    ShoreCoatingTarget, SurfaceAspect, SurfaceCoatingAction, SurfaceCoatingFacts, SurfaceCoatingReason,
)


class SurfaceCoatingPolicyDefinition(PolicyOwner):
    """Nominal terrain policy owner, independent of hydrology."""


class SurfaceCoatingCase(StrEnum):
    ROCK_CLIFF = "rock_cliff"
    TARGET = "target"


class SurfaceCoatingTargetFacts(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    target: FactValue[ShoreCoatingTarget]


SURFACE_COATING_POLICY = ValuePolicy[SurfaceCoatingAction, SurfaceCoatingReason](
    owner=SurfaceCoatingPolicyDefinition, behavior_type=SurfaceCoatingAction, reason_type=SurfaceCoatingReason,
    disabled_behavior=SurfaceCoatingAction.KEEP_EXISTING_SURFACE,
    fallback_rules=tuple(PolicyFallback(reason, SurfaceCoatingAction.KEEP_EXISTING_SURFACE, True)
                         for reason in PolicyIssueReason),
    cases=(PolicyCaseDeclaration(
        key=SurfaceCoatingCase.ROCK_CLIFF,
        conditions=(
            Equal(FactValueRef(FieldRef(lambda: SurfaceCoatingFacts, lambda f: f.aspect)), SurfaceAspect.RELIEF_FACE),
            Equal(FactValueRef(FieldRef(lambda: SurfaceCoatingFacts, lambda f: f.side_kind)), ReliefSideKind.SHEER),
            Equal(FactValueRef(FieldRef(lambda: SurfaceCoatingFacts, lambda f: f.substrate)), MaterialSubstrateKind.ROCK)),
        effect=DisableEffect(PolicyDisableReason.POLICY_FORBID), reason=SurfaceCoatingReason.ROCK_CLIFF,
        stage=PolicyStage.SUPPORT),
        PolicyCaseDeclaration(key=SurfaceCoatingCase.TARGET,
            conditions=(IsPresent(FactValueRef(FieldRef(lambda: SurfaceCoatingTargetFacts, lambda f: f.target))),),
            effect=SelectBehaviorEffect(SurfaceCoatingAction.APPLY_SHORE_SURFACE),
            reason=SurfaceCoatingReason.SUPPORTED)))


class SurfaceCoatingSelection(BaseModel, frozen=True):
    """Captured requested action; support and target proof constrain this selection."""
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    action: Annotated[SurfaceCoatingAction, SelectByValue(SURFACE_COATING_POLICY, (
        ValueCase(when=SurfaceCoatingAction.APPLY_SHORE_SURFACE,
                  behavior=SurfaceCoatingAction.APPLY_SHORE_SURFACE),))]
