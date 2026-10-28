"""Typed generation decision and private water policy explanations."""

from enum import StrEnum

from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.policy.policyDecision import ValueSelectionDecision


class WaterPolicyReason(StrEnum):
    DECLARED_ONLY = "declared_only"
    AUTORESOLVE = "autoresolve"
    DRY_TARGET = "dry_target"
    EMPTY_GENERATION_TARGET = "empty_generation_target"


type HydrologyGenerationDecision = ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason]
