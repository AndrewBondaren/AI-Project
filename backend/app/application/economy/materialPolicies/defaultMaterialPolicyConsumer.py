"""Default material policy consumer — tz_economic_tier.md §11.3.

Handles requests without an explicit policy: resolves the default through
the extensible `default_material_policy` helper (RICH → max strength, all
other bands → min), then delegates to the shared comparison mechanism in
MaterialPolicyConsumer — candidate comparison is not duplicated here.
"""

from app.application.economy.materialPolicies.defaultMaterialPolicy import (
    default_material_policy,
)
from app.application.economy.materialPolicies.materialPolicyConsumer import (
    MaterialPolicyConsumer,
)
from app.dataModel.economy.materialPolicies import (
    MaterialPolicyDecision,
    MaterialPolicyRequest,
)


class DefaultMaterialPolicyConsumer:
    """Resolves the policy from the caller-resolved building context."""

    def decide(self, request: MaterialPolicyRequest) -> MaterialPolicyDecision:
        resolved = request.model_copy(
            update={"policy": default_material_policy(request.context)})
        return MaterialPolicyConsumer().decide(resolved)
