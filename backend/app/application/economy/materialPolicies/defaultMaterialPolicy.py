"""Default material policy rule — tz_economic_tier.md §11.3.

Extensible helper of the default consumer: maps the resolved building
economic context to a strength policy. Rich buildings build with the
strongest candidate, every other band with the weakest. The band itself is
resolved by the caller through the existing §3 registry mapping — this
helper keeps no tier-name lists, no RNG and no candidate comparison; those
stay in the shared machinery used by DefaultMaterialPolicyConsumer.
"""

from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import (
    BuildingEconomicContext, MaterialPolicy,
)


def default_material_policy(context: BuildingEconomicContext) -> MaterialPolicy:
    """§11.3: RICH → max_strength; all other bands, incl. WEALTHY → min."""
    if context.band == EconomicTierBand.RICH:
        return MaterialPolicy.MAX_STRENGTH
    return MaterialPolicy.MIN_STRENGTH
