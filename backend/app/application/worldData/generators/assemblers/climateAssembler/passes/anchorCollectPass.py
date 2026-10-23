from app.application.worldData.generators.climate.anchorAssign import auto_anchors_from_features
from app.application.worldData.generators.climate.anchorCollect import (
    build_merged_field,
    collect_manual_anchors,
)
from app.application.worldData.generators.climate.anchorDetect import (
    ProminenceScale,
    detect_terrain_features,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.generators.coordinates import map_cell_fine_span
from app.application.worldData.generators.climate.anchorAssign import resolved_auto_anchors
from app.application.worldData.generators.climate.anchorCollect import merge_local_anchors
from app.application.worldData.generators.climate.anchorDetect import (
    grid_prominence_thresholds, terrain_feature_candidates, select_terrain_features,
)
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput, ProminenceThresholds
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, FineZ
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def run_anchor_collect_pass(
    world: World,
    locations: list[NamedLocation],
    heightmap_cells: list[MapCell],
    pole_field: ClimatePoleField,
) -> ClimateAnchorField:
    """Pass 2: local manual + terrain auto (zone from pole field), admin fallback."""
    cell_m   = map_cell_fine_span(world)
    uid_map  = {loc.location_uid: loc for loc in locations}
    manual   = collect_manual_anchors(locations, cell_m)
    features = detect_terrain_features(
        heightmap_cells, world.world_uid, scale=ProminenceScale.METRIC,
    )
    auto     = auto_anchors_from_features(features, world, uid_map, pole_field)
    return build_merged_field(
        manual, auto, locations, cell_m,
        world=world,
        include_admin_fallback=pole_field.is_empty(),
    )


def collect_resolved_local_anchors(inputs: ClimateLocalInput, base: ClimateBasePlan,
    surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]) -> PlanBuildResult[ClimateLocalPlan]:
    """Pure equivalent of the legacy synthetic-coarse collect pass."""
    policy = inputs.feature_policy
    heights: dict[tuple[int, int], int] = {(cell.gx, cell.gy): z for cell, z in surface_z}
    thresholds = (grid_prominence_thresholds(max(heights.values()) - min(heights.values()) if heights else 0)
        if policy.scale is ProminenceScale.GRID else
        ProminenceThresholds(peak=policy.peak_min, basin=policy.basin_min, liquid=policy.liquid_min))
    water = frozenset(heights) if policy.synthetic_surface_terrain == policy.water_feature_terrain else frozenset()
    candidates = terrain_feature_candidates(heights, water, thresholds)
    features = select_terrain_features(candidates, policy.max_features)
    auto = resolved_auto_anchors(features, base)
    anchors = merge_local_anchors(inputs.manual, auto, policy.manual_exclusion_grid)
    diagnostics: list[PlanDiagnostic] = []
    if len(candidates) > policy.max_features:
        diagnostics.append(PlanDiagnostic(issue=FieldPathError(("feature_policy", "max_features"),
            f"terrain features capped at {policy.max_features} (candidates={len(candidates)})",
            code="auto_features_capped"), disposition=PlanDiagnosticDisposition.NOTICE))
    if not anchors:
        if not base.poles:
            anchors = inputs.admin
        elif inputs.admin:
            diagnostics.append(PlanDiagnostic(issue=FieldPathError(("admin",),
                f"admin zones skipped (active pole tier); count={len(inputs.admin)}",
                code="admin_skipped_active_pole"), disposition=PlanDiagnosticDisposition.NOTICE))
    return PlanBuildResult[ClimateLocalPlan](payload=ClimateLocalPlan(anchors=anchors), diagnostics=tuple(diagnostics))
