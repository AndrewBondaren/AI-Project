import random

from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode


def generate_radial(
    slot:            DistrictSlot,
    skeleton:        SettlementSkeleton,
    world_uid:       str,
    connection_type: str,
    lanes_per_side:  int,
    has_sidewalk:    bool,
    rng:             random.Random,
    surface:         dict[tuple[int, int], int] | None = None,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    _ = surface
    raise NotImplementedError("radial layout — не реализован")
