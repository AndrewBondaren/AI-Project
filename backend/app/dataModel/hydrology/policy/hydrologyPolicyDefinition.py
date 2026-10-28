"""Hydrology generation metadata; models attach it, common policy compiles it (tz_policy §5)."""

from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyDeclaration import PolicyOwner, ValuePolicy


class HydrologyGenerationPolicy(PolicyOwner):
    """Nominal owner, independent of source model and execution scope."""


HYDROLOGY_GENERATION_POLICY = ValuePolicy[Mode, WaterPolicyReason](
    owner=HydrologyGenerationPolicy, behavior_type=Mode, reason_type=WaterPolicyReason,
    disabled_behavior=Mode.DISABLED)

HYDROLOGY_ENABLED = EnabledFor(HYDROLOGY_GENERATION_POLICY)
HYDROLOGY_AUTORESOLVE = SelectByValue(HYDROLOGY_GENERATION_POLICY, (
    ValueCase(when=False, behavior=Mode.DECLARED_ONLY, reason=WaterPolicyReason.DECLARED_ONLY),
    ValueCase(when=True, behavior=Mode.AUTORESOLVE, reason=WaterPolicyReason.AUTORESOLVE),
))
