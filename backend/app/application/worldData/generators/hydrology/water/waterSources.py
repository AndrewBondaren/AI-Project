"""Declared spec contexts and natural-only depression sources; no placement/carve."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.application.worldData.generators.hydrology.water.depressionTree import DepressionTree
from app.application.worldData.generators.hydrology.waterBodyIdentity import (
    AutoWaterBodyRole, auto_water_body_uid,
)
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.worldTopology import Coord, WorldTopology


@dataclass(frozen=True)
class WaterSource:
    spec: BasinSpec
    seeds: tuple[Coord, ...]
    authored: bool


def water_sources(surface_z: Mapping[Coord, int], specs: Sequence[BasinSpec],
                  tree: DepressionTree, topology: WorldTopology, policy: WorldHydrology,
                  *, auto_seas: bool, auto_lakes: bool) -> tuple[WaterSource, ...]:
    sources = []
    declared_nodes = set()
    for spec in sorted(specs, key=lambda item: item.source_uid):
        if any(cell not in surface_z for cell in spec.footprint):
            raise ValueError(f"unresolved water footprint: {spec.source_uid}")
        wet = {cell for cell in spec.footprint if surface_z[cell] < spec.z_water_level}
        # The declaration supplies the whole carved footprint. After a spill,
        # an internal ridge can separate its wet pockets; each pocket still
        # receives the body's common effective level, not just the deepest one.
        seeds = tuple(sorted(wet, key=lambda cell: (cell[1], cell[0])))
        declared_nodes.update(tree.by_cell[cell] for cell in wet)
        sources.append(WaterSource(spec, seeds, True))
    for index, node in enumerate(tree.nodes):
        if node.children or index in declared_nodes:
            continue
        anchor = min(node.cells, key=lambda cell: (cell[1], cell[0]))
        if node.height < policy.default_water_level and auto_seas:
            level = policy.default_water_level
            kind, bands, role = BasinKind.OCEAN, policy.default_seas.bands, AutoWaterBodyRole.SEA
        elif auto_lakes and node.spill is not None and node.spill > node.height:
            level = node.spill
            kind, bands, role = BasinKind.LAKE, policy.default_lakes.bands, AutoWaterBodyRole.LAKE
        else:
            continue
        sources.append(WaterSource(BasinSpec(
            source_uid=auto_water_body_uid(role, anchor), kind=kind,
            liquid=WaterBody.default_liquid(), footprint=frozenset(node.cells),
            z_water_level=level, floor_z=node.height, bands=bands,
        ), (anchor,), False))
    return tuple(sources)
