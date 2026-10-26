"""C22 building-shell cache for one settlement assembly.

Target (tz_structure_connections.md §5.1.3): cache holds envelopes ``w×h``
for packing. Interior rooms / ``StructureGeneratorService`` are not this
scope (city TZ phase 3). Envelope SoT = ``PlotLayoutTemplate.occupied_footprint``
on the plot drawing.

Cache keys are plot member ``template_uid`` + ``facing`` (B3): same-name
bodies from different packs never collide. Tests may inject layouts via
``from_south_map``.
"""

from __future__ import annotations

from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    PACKING_ENVELOPE_FACING,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingScope,
    PackingStep,
    packing_warning,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose
from app.db.models.world import World


def collect_building_template_uids(
    district_slots: list[DistrictSlot],
    world:          World,
    skeleton:       SettlementSkeleton,
    catalog:        BuildingCatalog,
    *,
    settlement_uid: str | None = None,
) -> set[str]:
    from app.application.worldData.generators.assemblers.districtAssembler.planner.tokens import (
        pick_layout_uids,
    )

    uids: set[str] = set()
    loc = settlement_uid or world.world_uid
    for slot in district_slots:
        rng = settlement_cell_rng(
            world.world_uid,
            loc,
            slot.cell_x,
            slot.cell_y,
            SettlementCellRngRole.BUILDINGS,
        )
        uids.update(pick_layout_uids(slot, world, skeleton, catalog, rng))
    return uids


class BuildingLayoutCache:
    """Key ``(template_uid, facing)``. Packing envelope is SOUTH (CONN-PACK-3)."""

    def __init__(self) -> None:
        self._layouts: dict[tuple[str, str], StructureLayout] = {}

    @classmethod
    def from_south_map(cls, layouts: dict[str, StructureLayout]) -> BuildingLayoutCache:
        """Test seam: keys are the caller-declared template uids."""
        cache = cls()
        for uid, layout in layouts.items():
            cache._layouts[(uid, PACKING_ENVELOPE_FACING.value)] = layout
        return cache

    def _key(self, template_uid: str, facing: Facing) -> tuple[str, str]:
        return (template_uid, facing.value)

    def get(
        self,
        template_uid: str,
        facing: Facing = PACKING_ENVELOPE_FACING,
    ) -> StructureLayout | None:
        return self._layouts.get(self._key(template_uid, facing))

    def envelope(self, template_uid: str) -> OccupiedFootprint | None:
        layout = self.get(template_uid, PACKING_ENVELOPE_FACING)
        if layout is None or layout.occupied_footprint is None:
            return None
        return layout.occupied_footprint

    def template_uids(self) -> list[str]:
        return sorted({uid for uid, _facing in self._layouts})

    def keys(self) -> list[str]:
        return self.template_uids()

    def __len__(self) -> int:
        return len(self.template_uids())

    def __contains__(self, template_uid: object) -> bool:
        if not isinstance(template_uid, str):
            return False
        return self.get(template_uid, PACKING_ENVELOPE_FACING) is not None

    def __getitem__(self, template_uid: str) -> StructureLayout:
        layout = self.get(template_uid, PACKING_ENVELOPE_FACING)
        if layout is None:
            raise KeyError(template_uid)
        return layout

    def ensure(
        self,
        template_uid: str | None,
        template: PlotLayoutTemplate,
        facing: Facing = PACKING_ENVELOPE_FACING,
        *,
        district: str | None = None,
        leaves: tuple[BuildingPurpose, ...] = (),
    ) -> StructureLayout | None:
        if not template_uid:
            return None
        cached = self.get(template_uid, facing)
        if cached is not None:
            return cached
        layout = _envelope_layout(
            template, template_uid, facing, district=district, leaves=leaves,
        )
        if layout is None:
            return None
        self._layouts[self._key(template_uid, facing)] = layout
        return layout


def build_layout_cache(
    world:          World,
    skeleton:       SettlementSkeleton,
    district_slots: list[DistrictSlot],
    catalog:        BuildingCatalog,
    *,
    settlement_uid: str | None = None,
) -> BuildingLayoutCache:
    """Pick drawings by member uid; envelopes from declared plot footprint."""
    cache = BuildingLayoutCache()
    for uid in sorted(
        collect_building_template_uids(
            district_slots, world, skeleton, catalog,
            settlement_uid=settlement_uid,
        ),
    ):
        entry = catalog.entry_for(uid)
        if entry is None:
            packing_warning(
                PackingStep.CACHE,
                district=PackingScope.CACHE,
                system_name=uid,
                reason=PackingReason.MISSING_TEMPLATE,
            )
            continue
        cache.ensure(
            uid, entry.body, PACKING_ENVELOPE_FACING,
            leaves=catalog.structures.leaves_of(entry.body),
        )
    return cache


def _envelope_layout(
    template: PlotLayoutTemplate,
    template_uid: str,
    facing: Facing,
    *,
    district: str | None = None,
    leaves: tuple[BuildingPurpose, ...] = (),
) -> StructureLayout | None:
    """Packing envelope from the plot drawing. Does not generate rooms."""
    spec = template.occupied_footprint
    if spec is None:
        packing_warning(
            district or PackingScope.CACHE,
            PackingStep.CACHE,
            system_name=template_uid,
            facing=facing.value,
            reason=PackingReason.STUB_NO_SHELL,
            structure_type=",".join(str(p) for p in leaves),
        )
        return None
    footprint = OccupiedFootprint(
        min_x=spec.min_x,
        min_y=spec.min_y,
        width=spec.width,
        depth=spec.depth,
    )
    return StructureLayout(
        cells=[],
        levels=[],
        transitions=[],
        rooms=[],
        occupied_footprint=footprint,
    )
