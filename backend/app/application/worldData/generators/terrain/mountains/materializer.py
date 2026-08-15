"""MountainMaskMaterializer — mask-domain plugin (tz_map_light_bake § MaskDomain materialize).

Not the DAG ``application/engine`` runtime — L0 mountain Spec → footprint → paint/z.
"""

from __future__ import annotations

from app.application.jsonValidation import terrain_masks as read_terrain_masks
from app.application.worldData.generators.terrain.mountains.collect import (
    autoresolve_mountain_specs,
    load_declared_mountains,
    merge_mountain_spec_sources,
    specs_from_geographic_locations,
)
from app.application.worldData.generators.terrain.relief.geom.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.mountains.reliefSidesStamp import (
    stamp_entries_from_relief,
)
from app.application.worldData.generators.terrain.mountains.formPipeline import (
    materialize_mountain_entry,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_mountain_surface_z,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import MaskFootprint
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.masks.enums.maskDomainId import MaskDomainId
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrainMasks.mountain.enums import MountainKind
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import (
    MountainsCategoryPolicy,
    WorldTerrainMasks,
)

MountainEntry = MountainSpec | MountainRangeSpec


class MountainMaskMaterializer:
    domain = MaskDomainId.MOUNTAINS

    def __init__(self) -> None:
        self._base_z: dict[tuple[int, int, int, int], int] = {}

    def begin_pass(self) -> None:
        self._base_z.clear()

    def category_policy(self, masks: WorldTerrainMasks) -> MountainsCategoryPolicy:
        return masks.default_mountains

    def load_declared(self, ctx: LightGridBakeContext) -> list[MountainEntry]:
        return load_declared_mountains(read_terrain_masks(ctx.world))

    def load_anchor_specs(self, ctx: LightGridBakeContext) -> list[MountainEntry]:
        policy = read_terrain_masks(ctx.world).default_mountains
        return list(specs_from_geographic_locations(ctx.locations, policy))

    def autoresolve_specs(
        self,
        ctx: LightGridBakeContext,
        policy: MaskCategoryPolicy,
    ) -> list[MountainEntry]:
        if not isinstance(policy, MountainsCategoryPolicy):
            raise TypeError(
                f"mountains autoresolve expects MountainsCategoryPolicy, got {type(policy)!r}"
            )
        reserved: list[MountainEntry] = list(self.load_declared(ctx)) + list(
            self.load_anchor_specs(ctx)
        )
        return list(autoresolve_mountain_specs(ctx, policy, reserved=reserved))

    def collect(
        self,
        ctx: LightGridBakeContext,
        policy: MaskCategoryPolicy,
    ) -> list[MountainEntry]:
        # Q17: same merge SoT as coarse (`merge_mountain_spec_sources`)
        if not isinstance(policy, MountainsCategoryPolicy):
            raise TypeError(
                f"mountains collect expects MountainsCategoryPolicy, got {type(policy)!r}"
            )
        declared = self.load_declared(ctx)
        anchors = self.load_anchor_specs(ctx)
        auto: list[MountainEntry] = []
        if policy.autoresolve:
            reserved: list[MountainEntry] = list(declared) + list(anchors)
            auto = list(autoresolve_mountain_specs(ctx, policy, reserved=reserved))
        merged = merge_mountain_spec_sources(
            declared=declared, anchors=list(anchors), auto=auto,
        )
        seed = bake_seed(ctx.world)
        return stamp_entries_from_relief(
            merged,
            world=ctx.world,
            world_seed=seed,
            templates_by_uid=ctx.relief_templates_by_uid,
        )

    def materialize(self, spec: MountainEntry, scale: LightGridScale) -> MaskFootprint:
        return materialize_mountain_entry(spec, scale)

    def apply(
        self,
        compose: LightGridCompose,
        footprint: MaskFootprint,
        spec: MountainEntry,
        masks: WorldTerrainMasks,
        *,
        tile_set: set[tuple[int, int]],
        ctx: LightGridBakeContext,
    ) -> None:
        policy = masks.default_mountains
        apply_terrain_footprint(
            compose,
            footprint,
            system_terrain=policy.system_terrain,
            masks=masks,
            tile_set=tile_set,
            preserve_hydro=True,
        )
        kind: MountainKind = spec.kind
        self._apply_elevation(
            compose, footprint, kind=kind, policy_terrain=policy.system_terrain,
            tile_set=tile_set, ctx=ctx,
        )

    def _apply_elevation(
        self,
        compose: LightGridCompose,
        footprint: MaskFootprint,
        *,
        kind: MountainKind,
        policy_terrain: str,
        tile_set: set[tuple[int, int]],
        ctx: LightGridBakeContext,
    ) -> None:
        z_min = world_z_min(ctx.world)
        z_max = world_z_max(ctx.world)
        for ref in footprint.cells:
            if (ref.gx, ref.gy) not in tile_set:
                continue
            cell = compose.get(ref.gx, ref.gy, ref.tx, ref.ty)
            if cell is None:
                continue
            if cell.system_terrain != policy_terrain:
                continue
            key4 = (ref.gx, ref.gy, ref.tx, ref.ty)
            if key4 not in self._base_z:
                self._base_z[key4] = cell.surface_z
            frac = float(footprint.elevation_fraction.get(ref, 1.0))
            new_z = resolve_mountain_surface_z(
                self._base_z[key4],
                z_min=z_min,
                z_max=z_max,
                kind=kind,
                side_fraction=frac,
            )
            if new_z > cell.surface_z:
                cell.surface_z = new_z
            face = footprint.system_facing.get(ref)
            if face is not None:
                cell.system_facing = face
