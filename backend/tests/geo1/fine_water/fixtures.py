from copy import replace

from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings
from app.dataModel.placement.result import PlacementBatchResultV2
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.worldBounds import WorldBounds
from tests.geo1.boundaries.fixtures import accepted
from tests.geo1.coating.fixtures import envelope
from tests.geo1.integration.support.pipeline import view
from tests.geo1.terrain_base.fixtures import inputs


def physical_inputs(topology):
    grid = inputs()[0].grid
    bounds, span = topology.bounds, grid.fine_span
    macro = WorldTopology(mode=topology.mode, bounds=WorldBounds(
        x_min=bounds.x_min // span, y_min=bounds.y_min // span,
        x_max=bounds.x_max // span, y_max=bounds.y_max // span))
    return replace(view().hydrology, grid=grid, topology=macro, z_min=-20, z_max=40, change_uid="fine-operation")


def decisions(physical, auto=False, enabled=True):
    return tuple((category, PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts,
        mode=physical.resolution_mode)) for category in sorted(Category, key=lambda c: c.value)
        for binding in (bind_hydrology_generation_policy(enabled=enabled,
            generation=WorldWaterGenerationSettings(autoresolve=auto), defaults=physical.defaults,
            category=getattr(physical, category.value + "_generation"), root_path=("hydrology",),
            context_path=("classification", category.value)),))


def placement(window, specs):
    return envelope("accepted_native", PlacementBatchResultV2(world_uid=window.ref.key.world_uid,
        snapshot_uid="regions", snapshot_revision=window.ref.output_fingerprint,
        results=tuple(accepted(s.source_uid, s.source_uid + "-region", s.footprint) for s in specs)),
        (PlanDependency(slot="pre_water_surface", ref=window.ref),))
