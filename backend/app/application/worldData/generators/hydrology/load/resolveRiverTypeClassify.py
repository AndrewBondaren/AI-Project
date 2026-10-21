"""Read the validated classification POJO; defaults and errors belong to jsonValidation."""

from app.application.jsonValidation.worldRow import hydrology
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.db.models.world import World


def resolve_river_type_classify(world: World) -> RiverTypeClassify:
    return hydrology(world).default_rivers.type_classify
