"""Collect final hydrology observations without executing admission or placement."""

from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPolicyFacts, HydrologyPolicySnapshot, WaterPlacementPolicySource,
)
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.policy.policyEnums import PolicySupportState
from app.dataModel.policy.policyFacts import FactValue, KnownFact, UnknownFact
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def collect_hydrology_policy_facts(
    source: WaterPlacementPolicySource, snapshot: HydrologyPolicySnapshot,
) -> HydrologyPolicyFacts:
    """Observe supplied source-to-body mapping, never location/declared-basin UID aliases."""
    if not isinstance(snapshot, HydrologyPolicySnapshot):
        raise ValueError("hydrology observations require a typed snapshot")
    snapshot = HydrologyPolicySnapshot.model_validate(snapshot)
    value = source if isinstance(source, DeclaredCoastline) else source.value
    kind = BasinKind.LAKE if isinstance(value, DeclaredLake) else value.kind
    category = (WaterGenerationCategory.LAKE if kind is BasinKind.LAKE else
                WaterGenerationCategory.OCEAN if kind is BasinKind.OCEAN else WaterGenerationCategory.SEA)
    purpose = value.purpose if isinstance(value, DeclaredCoastline) else CoastlinePurpose.WATER_SOURCE
    water: FactValue[bool | None] = KnownFact[bool | None](value=None)
    if isinstance(value, DeclaredCoastline) and purpose is CoastlinePurpose.BODY_BOUNDARY:
        target = value.target_source_uid
        if target is None:
            raise ValueError("normalized boundary requires target source UID")
        support = next((entry for entry in snapshot.supports if entry.uid == target), None)
        # Non-accepted support belongs to the generic engine. None here is inapplicable,
        # not a dry verdict or a second implementation of support policy.
        if support is not None and support.state is PolicySupportState.ACCEPTED:
            mapping = snapshot.source_mapping
            entry = next((entry for entry in mapping.entries if entry.source_uid == target), None) if mapping else None
            plan = snapshot.hydrology.payload if snapshot.hydrology is not None else None
            if entry is None or plan is None:
                water = _unknown(target, "accepted source requires final hydrology and explicit source mapping")
            elif not entry.body_uids:
                water = KnownFact[bool | None](value=False)
            elif not set(entry.body_uids).issubset(body.water_body_uid for body in plan.water_bodies):
                water = _unknown(target, "source mapping references absent physical bodies")
            else:
                water = KnownFact[bool | None](value=any(
                    cell.liquid_candidate and cell.water_body_uid in entry.body_uids
                    for _, cell in (*plan.coarse_hydro, *plan.sparse_fine_hydro)))
    return HydrologyPolicyFacts(purpose=purpose, category=category, target_has_water=water)


def _unknown(target: str, message: str) -> UnknownFact:
    return UnknownFact(issue=FieldPathError(
        path=("hydrology", "source_mapping", target), message=message, code="unknown_fact"))
