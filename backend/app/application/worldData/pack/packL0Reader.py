"""L0 sample / surface read helpers — shared by gameplay merge and debug export."""

from __future__ import annotations

from app.application.jsonValidation import terrain_system_keys
from app.application.worldData.generators.terrain.terrainZ import subsurface_terrain_at_z
from app.application.worldData.generators.terrain.worldMapSettings import n_base, world_z_min
from app.application.worldData.pack.packMapHelpers import l0_sample_index, world_tile_size_m
from app.application.worldData.pack.packReadContext import PackReadContext
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.worldPack.hydrologyMaskWire import L0HydrologyRole
from app.dataModel.worldPack.layerPriority import MapLayerKind
from app.dataModel.worldPack.mergeMapCells import (
    CellContribution,
    LayerSlice,
    MergedCellView,
    merge_layers,
)
from app.application.worldData.pack.mapCellFromMerged import merged_view_to_map_cell
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.mapCell import MapCell
from app.db.models.world import World


class PackL0Reader:
    def __init__(self, context: PackReadContext) -> None:
        self._ctx = context

    def apply_climate(self, world: World, view: MergedCellView) -> MergedCellView:
        field = self._ctx.climate_field(world)
        if field is None:
            return view
        sample = field.sample_at(view.x, view.y)
        if sample is None:
            return view
        updates: dict = {}
        if view.temperature_base is None and sample.temperature_base is not None:
            updates["temperature_base"] = sample.temperature_base
        if view.rainfall is None and sample.rainfall is not None:
            updates["rainfall"] = sample.rainfall
        if not updates:
            return view
        return view.model_copy(update=updates)

    def sample_l0(self, world: World, gx: int, gy: int, tx: int, ty: int) -> WorldMapCellWire | None:
        reader = self._ctx.reader_for(world)
        try:
            _side, cells = reader.read_l0_tile(gx, gy)
        except FileNotFoundError:
            return None
        return next((c for c in cells if c.tx == tx and c.ty == ty), None)

    def l0_contribution(
        self,
        world: World,
        gx: int,
        gy: int,
        lx: int,
        ly: int,
        x: int,
        y: int,
        z: int,
    ) -> CellContribution | None:
        reader = self._ctx.reader_for(world)
        try:
            side, cells = reader.read_l0_tile(gx, gy)
        except FileNotFoundError:
            return None
        tile_size = world_tile_size_m(world)
        tx = l0_sample_index(lx, tile_size, side)
        ty = l0_sample_index(ly, tile_size, side)
        cell = next((c for c in cells if c.tx == tx and c.ty == ty), None)
        if cell is None:
            return None
        terrain_set = terrain_system_keys(world)
        surface_z = cell.surface_z
        depth = n_base(world)
        if z == surface_z:
            hydro = None
            if cell.hydrology_role != L0HydrologyRole.NONE:
                role = cell.hydrology_role.to_fine_role()
                hydro = {
                    "role": role.value if role else None,
                    "liquid_candidate": role is not None and role.is_open_water_role(),
                }
            return CellContribution(
                x=x,
                y=y,
                z=z,
                system_terrain=self._resolve_l0_terrain(world, cell),
                hydrology=hydro,
            )
        if surface_z - depth <= z < surface_z:
            return CellContribution(
                x=x,
                y=y,
                z=z,
                system_terrain=subsurface_terrain_at_z(terrain_set),
            )
        return None

    def surface_cells_for_tile(
        self,
        world: World,
        gx: int,
        gy: int,
        tile_size: int,
    ) -> list[MapCell]:
        reader = self._ctx.reader_for(world)
        try:
            side, cells = reader.read_l0_tile(gx, gy)
        except FileNotFoundError:
            return []
        if side <= 0:
            return []
        bucket = max(1, tile_size // side)
        out: list[MapCell] = []
        for wire in cells:
            lx = wire.tx * bucket + bucket // 2
            ly = wire.ty * bucket + bucket // 2
            x = gx * tile_size + lx
            y = gy * tile_size + ly
            z = wire.surface_z
            l0 = self.l0_contribution(world, gx, gy, lx, ly, x, y, z)
            if l0 is None:
                continue
            merged = self.apply_climate(
                world,
                merge_layers(x, y, z, [LayerSlice(kind=MapLayerKind.L0, cell=l0)]),
            )
            if merged.has_any_data():
                out.append(merged_view_to_map_cell(world.world_uid, merged))
        return out

    def _default_surface_terrain(self, world: World) -> str:
        registry = WorldTerrainRegistry.canonical_defaults()
        entry = registry.entry_for("plains")
        if entry is not None:
            return entry.system_terrain
        keys = terrain_system_keys(world)
        if keys:
            return next(iter(sorted(keys)))
        return registry.root[0].system_terrain

    def _resolve_l0_terrain(self, world: World, cell: WorldMapCellWire) -> str:
        if cell.system_terrain:
            return cell.system_terrain
        return self._default_surface_terrain(world)
