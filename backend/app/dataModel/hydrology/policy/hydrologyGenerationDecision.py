"""Typed generation decision and private water policy explanations."""

from enum import StrEnum

from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, ValueSelectionDecision
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


class WaterPolicyReason(StrEnum):
    DECLARED_ONLY = "declared_only"
    AUTORESOLVE = "autoresolve"
    DRY_TARGET = "dry_target"
    EMPTY_GENERATION_TARGET = "empty_generation_target"


type HydrologyGenerationDecision = ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason]
type WaterDesignDecision = ObjectAdmissionDecision[DesignedWaterStrategyKind, WaterPolicyReason]
