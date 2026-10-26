"""Material policy consumer — tz_economic_tier.md §11.

Applies an explicitly passed policy to prepared candidates. The §11.3
strength comparison lives here once: DefaultMaterialPolicyConsumer resolves
its policy through the helper and delegates to this class, so the comparison
is never duplicated. No RNG, no registry/DB lookups, no geometry.
"""

from app.dataModel.economy.materialPolicies import (
    MaterialCandidate,
    MaterialPolicy,
    MaterialPolicyDecision,
    MaterialPolicyFailure,
    MaterialPolicyRequest,
)


class MaterialPolicyConsumer:
    """Explicit-policy consumer — the shared §11.3 comparison mechanism."""

    def decide(self, request: MaterialPolicyRequest) -> MaterialPolicyDecision:
        if request.policy is None:
            raise ValueError(
                "MaterialPolicyConsumer requires an explicit policy; "
                "route policy=None to DefaultMaterialPolicyConsumer")
        policy = request.policy
        candidates = request.candidates
        if not candidates:
            return MaterialPolicyDecision(
                policy=policy, failure=MaterialPolicyFailure.NO_CANDIDATES,
                reason="request carries no candidates")
        missing = [c.system_material for c in candidates
                   if c.structural_strength is None]
        if missing:
            # §11.5: unavailable strength is a failure, never a silent zero.
            return MaterialPolicyDecision(
                policy=policy, failure=MaterialPolicyFailure.MISSING_STRENGTH,
                reason="structural_strength unavailable for: "
                       + ", ".join(missing))

        def rank(c: MaterialCandidate) -> tuple[float, int]:
            strength = c.structural_strength
            if policy == MaterialPolicy.MIN_STRENGTH:
                strength = -strength
            # §11.3: equal strength → larger source_area; max() keeps the
            # first maximal candidate — the caller-deterministic order.
            return (strength, c.source_area)

        winner = max(candidates, key=rank)
        return MaterialPolicyDecision(
            candidate=winner, policy=policy,
            reason=f"{policy.value}: {winner.system_material} "
                   f"(strength={winner.structural_strength}, "
                   f"source={winner.source_key})")
