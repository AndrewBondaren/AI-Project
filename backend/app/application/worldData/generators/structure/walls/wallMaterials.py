"""Wall material selector — tz_building_generator.md §8.7.1.

Maps each classified `WallRegion` to its material: the exterior shell takes
the building material; an interior partition takes the wall material of its
single adjacent room, or — when several rooms share it — the winner decided
by the material policy consumer layer (tz_economic_tier.md §11). The
shaft-enclosure material source is resolved here once by the same adjacency
rule, not in placers or cellBuilder. The selector only prepares candidates
and context; it never compares strength itself.
"""

from dataclasses import dataclass
from typing import Mapping

from app.application.economy.materialPolicies.defaultMaterialPolicyConsumer import (
    DefaultMaterialPolicyConsumer,
)
from app.application.economy.materialPolicies.materialPolicyConsumer import (
    MaterialPolicyConsumer,
)
from app.application.worldData.generators.structure.room.roomInstance import (
    _RoomInstance,
)
from app.dataModel.economy.materialPolicies import (
    BuildingEconomicContext,
    MaterialCandidate,
    MaterialPolicy,
    MaterialPolicyFailure,
    MaterialPolicyRequest,
)
from app.dataModel.locations.structure.wallRegion import (
    WallProvenance,
    WallRegion,
)


@dataclass(frozen=True)
class RegionMaterialChoice:
    """Material chosen for one region — consumed by the single wall writer."""
    region: WallRegion
    system_material: str


@dataclass(frozen=True)
class RegionMaterialFailure:
    """Interior region without a decidable material — the caller decides."""
    region: WallRegion
    failure: MaterialPolicyFailure
    reason: str


@dataclass(frozen=True)
class WallMaterialPlan:
    """Selector output: per-region materials plus structured failures."""
    choices: tuple[RegionMaterialChoice, ...]
    failures: tuple[RegionMaterialFailure, ...]


def select_wall_materials(
    regions: list[WallRegion],
    rooms_by_key: Mapping[str, _RoomInstance],
    building_material: str,
    material_strengths: Mapping[str, float | None],
    context: BuildingEconomicContext,
    policy: MaterialPolicy | None = None,
) -> WallMaterialPlan:
    """Choose one material per region — §8.7.1 rules, §11 policy layer.

    `material_strengths` is the caller-prepared lookup (MAT-T-1 zone); a
    missing entry means unavailable strength, which the consumer reports as
    a structured failure instead of treating it as zero. `policy` is the
    §11.5 stub: no authored source exists yet, callers pass None.
    """
    choices: list[RegionMaterialChoice] = []
    failures: list[RegionMaterialFailure] = []
    for region in regions:
        if region.provenance == WallProvenance.EXTERIOR:
            choices.append(RegionMaterialChoice(region, building_material))
        elif not region.room_keys:
            failures.append(RegionMaterialFailure(
                region, MaterialPolicyFailure.NO_CANDIDATES,
                "interior region without adjacent non-shaft rooms"))
        elif len(region.room_keys) == 1:
            # Single candidate — the consumer is not invoked (§8.7.1).
            choices.append(RegionMaterialChoice(
                region, rooms_by_key[region.room_keys[0]].wall_material))
        else:
            candidates = tuple(MaterialCandidate(
                system_material=rooms_by_key[key].wall_material,
                structural_strength=material_strengths.get(
                    rooms_by_key[key].wall_material),
                source_key=key,
                source_area=len(rooms_by_key[key].get_footprint()),
            ) for key in region.room_keys)
            request = MaterialPolicyRequest(
                candidates=candidates, policy=policy, context=context)
            # TODO: отключить прямое подключение консьюмеров политики материалов и вывести в DAG
            consumer = (MaterialPolicyConsumer() if request.policy is not None
                        else DefaultMaterialPolicyConsumer())
            decision = consumer.decide(request)
            if decision.candidate is not None:
                choices.append(RegionMaterialChoice(
                    region, decision.candidate.system_material))
            else:
                failures.append(RegionMaterialFailure(
                    region, decision.failure, decision.reason))
    return WallMaterialPlan(tuple(choices), tuple(failures))
