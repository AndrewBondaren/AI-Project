import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode


def generate_cul_de_sac(
    slot:            DistrictSlot,
    skeleton:        CitySkeleton,
    world_uid:       str,
    connection_type: str,
    lanes_per_side:  int,
    has_sidewalk:    bool,
    rng:             random.Random,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    raise NotImplementedError("cul_de_sac layout — не реализован")
