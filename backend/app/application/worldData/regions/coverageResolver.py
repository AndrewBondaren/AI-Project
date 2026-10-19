"""Pure eligibility scorer, with diagnostics only; never mutates region state."""

import logging
from dataclasses import dataclass
from math import fsum, isfinite

from app.application.worldData.regions.regionFacts import RegionFacts
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey, WorldTerrainRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetCoverage:
    target_key: TerrainKey
    strength: float


def _evaluate(rule: EligibilityRule, value: float | bool | None) -> tuple[bool, float]:
    """Hard inclusive predicate and soft satisfaction are deliberately separate.

    gte/lte: threshold = 1/2, linear ramp over max(abs(threshold), 1).
    in_range: plateau inside, linear falloff over one range width outside.
    This also defines zero/negative thresholds and degenerate ranges.
    """
    if value is None or not isfinite(value):
        return False, 0.0
    if rule.op == EligibilityOp.FLAG:
        return bool(value), float(bool(value))
    if rule.op == EligibilityOp.GTE:
        passed = value >= rule.lo
        satisfaction = 0.5 + (value - rule.lo) / (2 * max(abs(rule.lo), 1.0))
    elif rule.op == EligibilityOp.LTE:
        passed = value <= rule.hi
        satisfaction = 0.5 + (rule.hi - value) / (2 * max(abs(rule.hi), 1.0))
    else:
        passed = rule.lo <= value <= rule.hi
        distance = max(rule.lo - value, value - rule.hi, 0.0)
        satisfaction = 1.0 - distance / max(rule.hi - rule.lo, 1.0)
    return passed, min(1.0, max(0.0, satisfaction))


def resolve(region_facts: RegionFacts, registry: WorldTerrainRegistry) -> TargetCoverage | None:
    """Argmax raw weighted score; ties use ascending terrain key, never input order.

    strength = winning score / sum of that candidate's weights (zero if no
    positive weights). Only score > 0 wins: an all-zero board is unresolved,
    not a lexical-min pick. None means unresolved: the caller must retain its
    type. Region/cell aggregation belongs to fact consumers, not this function.
    """
    candidates = []
    rejected = []
    for entry in registry.root:
        evaluations = [(rule, *_evaluate(rule, region_facts.value_for(rule.fact)))
                       for rule in entry.eligibility]
        if any(rule.required and not passed for rule, passed, _ in evaluations):
            rejected.append(entry.system_terrain)
            continue
        score = fsum(rule.weight * satisfaction for rule, _, satisfaction in evaluations)
        score_max = fsum(rule.weight for rule in entry.eligibility)
        candidates.append((score, entry.system_terrain, score / score_max if score_max else 0.0))
    if not candidates:
        logger.warning(
            "landcover | resolve_unresolved | WarningError | reason=no_eligible_candidates rejected=%s",
            sorted(rejected),
        )
        return None
    score, target, strength = min(candidates, key=lambda item: (-item[0], item[1]))
    if score <= 0:
        logger.warning(
            "landcover | resolve_unresolved | WarningError | reason=zero_score candidates=%s",
            sorted(key for _, key, _ in candidates),
        )
        return None
    logger.debug("landcover | resolve_target | target=%s score=%s strength=%s facts=%s",
                 target, score, strength, region_facts)
    return TargetCoverage(target_key=target, strength=strength)
