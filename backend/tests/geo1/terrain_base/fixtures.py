from copy import replace

from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks, MountainsCategoryPolicy, RavinesCategoryPolicy
from app.dataModel.terrainMasks.mountain.specs import MountainSpec, MountainFormBySides
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from tests.geo1.hill_hosts.test_hosts import bases, coverage
from tests.geo1.support_sources.fixtures import captured


class Control:
    def raise_if_shutdown(self):
        pass


def inputs(*, mountain=True, hills=True):
    grid = SurfaceGridSettings(fine_span=16, light_side=4)
    masks = WorldTerrainMasks(default_mountains=MountainsCategoryPolicy(autoresolve=False),
                              default_ravines=RavinesCategoryPolicy(enabled=False))
    support = captured(grid=grid, masks=masks,
        refine_policy=ParentLightRefinePolicy(detail_noise_amplitude=0))
    policy = HillPolicy(min_spacing=6, radius=2, height=3, shapes=("circle",)) if hills else None
    support = replace(support, terrain_entries=tuple(replace(e, hills=policy) for e in support.terrain_entries))
    climate, terrain = bases()
    base = TerrainBaseInput(seed=support.seed, grid=grid, bbox=terrain.payload.bbox, z_min=-20, z_max=40)
    peak = MountainSpec(origin_x_m=8, origin_y_m=8, radius_m=4, form=MountainFormBySides(side_count=4),
                        sides=tuple({"kind": "sheer"} for _ in range(4)))
    relief = ReliefPlanInput(seed=base.seed, masks_enabled=True, mountains=masks.default_mountains,
        ravines=masks.default_ravines, declared_mountains=(peak,) if mountain else (), anchors=(), grid=grid,
        z_min=base.z_min, z_max=base.z_max, mountain_templates=(), mountain_pick=ReliefContextPickPolicy(), terrain_merge=())
    return base, relief, support, climate, terrain


def prepare(values=None, cells=None, control=None):
    return PreWaterTerrainPlanner().prepare("world", *(values or inputs()),
        cells=cells or coverage(0, 32, 0, 32), control=control or Control())
