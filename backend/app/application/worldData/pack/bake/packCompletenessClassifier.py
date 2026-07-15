"""Pack completeness classifier — expected vs baked (WP-28)."""

from __future__ import annotations

import json

from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
    prepare_surface_terrain_context,
)
from app.application.worldData.pack.bake.packTilePlanner import PackTilePlanner
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.packCompleteness import (
    PackCompleteness,
    PackCompletenessSnapshot,
)
from app.dataModel.worldPack.packTilePlan import PackTileRef
from app.dataModel.worldPack.worldPackManifest import WorldPackManifest
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _locations_expected_from_index(index: LocationsIndexWire | None) -> list[str]:
    if index is None:
        return []
    return [p.location_uid for p in index.locations]


class PackCompletenessClassifier:
    def __init__(self, planner: PackTilePlanner | None = None) -> None:
        self._planner = planner or PackTilePlanner()

    def classify(
        self,
        world: World,
        locations: list[NamedLocation],
        *,
        manifest: WorldPackManifest | None,
        surface_ctx: SurfaceTerrainContext | None = None,
        locations_index: LocationsIndexWire | None = None,
        max_missing_list: int = 64,
    ) -> PackCompletenessSnapshot:
        if manifest is None or not manifest.tiles:
            return PackCompletenessSnapshot(completeness="absent")

        ctx = surface_ctx
        if ctx is None:
            ctx = prepare_surface_terrain_context(world, locations)
        if ctx is None:
            return PackCompletenessSnapshot(completeness="partial")

        light_plan = self._planner.plan(
            world, locations, ctx, scope="light", max_tiles=None,
        )
        full_plan = self._planner.plan(
            world, locations, ctx, scope="full",
        )
        baked = {
            (t.gx, t.gy)
            for t in manifest.tiles
            if t.world_map_path
        }
        expected_light = {t.as_tuple() for t in light_plan.tiles}
        expected_full = {t.as_tuple() for t in full_plan.tiles}

        missing_full = sorted(expected_full - baked, key=lambda t: (t[1], t[0]))
        light_ok = expected_light <= baked
        full_ok = expected_full <= baked

        detailed_uids = {
            e.location_uid
            for e in manifest.location_terrain_entries
            if e.terrain_path
        }
        expected_locs = _locations_expected_from_index(locations_index)
        if not expected_locs:
            # Fallback: locations with map anchors
            expected_locs = [
                loc.location_uid
                for loc in locations
                if loc.map_x is not None and loc.map_y is not None
            ]
        missing_detailed = [uid for uid in expected_locs if uid not in detailed_uids]
        detailed_ok = len(missing_detailed) == 0 and len(expected_locs) > 0

        completeness: PackCompleteness
        if full_ok and detailed_ok:
            completeness = "full_detailed_complete"
        elif full_ok:
            completeness = "full_complete"
        elif light_ok:
            completeness = "light_complete"
        else:
            completeness = "partial"

        return PackCompletenessSnapshot(
            completeness=completeness,
            expected_l0_light=len(expected_light),
            expected_l0_full=len(expected_full),
            l0_baked=len(baked),
            locations_expected=len(expected_locs),
            locations_detailed=len(detailed_uids),
            missing_l0_full=[
                PackTileRef(gx=gx, gy=gy)
                for gx, gy in missing_full[:max_missing_list]
            ],
            missing_detailed=missing_detailed[:max_missing_list],
        )

    @staticmethod
    def load_locations_index(reader) -> LocationsIndexWire | None:
        path = reader.paths.locations_index_path()
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LocationsIndexWire.model_validate(raw)
