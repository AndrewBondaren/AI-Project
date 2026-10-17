"""Surface neighbor policy — tz_terrain_generation § Форма мира.

Coordinate arithmetic belongs to WorldBounds; this policy selects the map.
No bake/halo/movement consumer is wired here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.dataModel.spatial.facing import CARDINAL_FACINGS, NS_FACINGS, Facing, opposite
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.worldPack.wire.worldBounds import WorldBounds
from app.dataModel.worldPack.wire.worldTopologyMode import WorldTopologyMode

Coord = tuple[int, int]


class NeighborResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    coord: Coord
    edge_crossing: bool
    invert_dy: bool


class SeamPair(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner: Coord
    other: Coord
    owner_facing: Facing
    other_facing: Facing
    invert_dy: bool


class WorldTopology(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: WorldTopologyMode = Field(
        default_factory=lambda: WorldTerrainScalars.canonical_defaults().world_topology_mode,
    )
    bounds: WorldBounds

    @field_validator("bounds")
    @classmethod
    def resolve_bounds(cls, bounds: WorldBounds, info: ValidationInfo) -> WorldBounds:
        if info.data.get("mode") is WorldTopologyMode.SPHERE:
            return bounds.even_width()
        return bounds

    def grid_neighbor(self, x: int, y: int, facing: Facing) -> Coord | None:
        """Delegate the existing non-wrapped AABB lookup, with its original API."""
        return self.bounds.grid_neighbor(x, y, facing)

    def neighbor(self, x: int, y: int, facing: Facing) -> NeighborResult | None:
        facing = Facing(facing)
        if facing not in CARDINAL_FACINGS:
            raise ValueError("surface topology requires a cardinal Facing")
        if not self.bounds.contains(x, y):
            return None
        coord = self.grid_neighbor(x, y, facing)
        if coord is not None:
            return NeighborResult(coord=coord, edge_crossing=False, invert_dy=False)
        if self.mode is WorldTopologyMode.PLANAR:
            return None
        invert_dy = self.mode is WorldTopologyMode.SPHERE and facing in NS_FACINGS
        coord = (self.bounds.half_width_partner(x, y) if invert_dy
                 else self.bounds.antagonist_tile(x, y, facing))
        if coord is None:
            raise RuntimeError("in-bounds edge has no topology partner")
        return NeighborResult(coord=coord, edge_crossing=True, invert_dy=invert_dy)

    def antagonist_tile(self, x: int, y: int, facing: Facing) -> Coord | None:
        """Coordinate-only edge lookup; delegates neighbor's selected map."""
        result = self.neighbor(x, y, facing)
        return result.coord if result is not None and result.edge_crossing else None

    def canonicalize(self, x: int, y: int) -> Coord | None:
        if self.mode is WorldTopologyMode.PLANAR:
            return (x, y) if self.bounds.contains(x, y) else None
        if self.mode is WorldTopologyMode.SPHERE:
            return self.bounds.folded_coordinate(x, y)
        return self.bounds.wrapped_coordinate(x, y)

    def seam_pairs(self) -> tuple[SeamPair, ...]:
        """Stable owner→other pairs; retain distinct faces between the same tiles."""
        if self.mode is WorldTopologyMode.PLANAR:
            return ()
        pairs: set[SeamPair] = set()
        for x, y, facing in self.bounds.edge_tiles():
            result = self.neighbor(x, y, facing)
            if result is None or result.coord == (x, y):
                continue
            owner, other = sorted(((x, y), result.coord))
            partner_facing = facing if result.invert_dy else opposite(facing)
            owner_facing, other_facing = ((facing, partner_facing) if owner == (x, y)
                                          else (partner_facing, facing))
            pairs.add(SeamPair(
                owner=owner, other=other, owner_facing=owner_facing,
                other_facing=other_facing, invert_dy=result.invert_dy,
            ))
        return tuple(sorted(pairs, key=lambda pair: (
            pair.owner, pair.other, pair.owner_facing.value, pair.other_facing.value,
        )))
