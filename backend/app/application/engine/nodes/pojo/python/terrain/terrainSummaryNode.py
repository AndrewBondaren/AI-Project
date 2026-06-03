import logging
from dataclasses import dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.core.appSettings import app_settings
from app.core.distanceUnit import DistanceUnit

_CONVERSION: dict[DistanceUnit, float] = {
    DistanceUnit.METERS: 1.0,
    DistanceUnit.FEET:   3.28084,
    DistanceUnit.YARDS:  1.09361,
}

logger = logging.getLogger(__name__)


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class TerrainSummaryNode(PythonNode):
    """
    Агрегирует сырые MapCells из shared_context["terrain"] в семантику для LLM.
    Потребители: SceneNarrationNode, SceneCombatNode и т.п.
    raw cells остаются в shared_context для движка физики/движения.
    """

    id:   str = "terrain_summary"
    name: str = "Terrain Summary"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["terrain_context"])
    possible_errors: list = field(default_factory=list)

    async def execute(self, state, context) -> NodeResult:
        terrain = state.shared_context.get("terrain", {})
        cells   = terrain.get("cells", [])

        location_uid = terrain.get("location_uid")

        unit      = app_settings.distance_unit
        factor    = _CONVERSION[unit] * app_settings.cell_size

        if not cells:
            logger.debug("terrain_summary | no cells for location=%s", location_uid)
            return NodeResult(data={
                "location_uid":      location_uid,
                "terrain_types":     [],
                "materials":         [],
                "has_structural":    False,
                "danger_levels":     [],
                "travel_difficulty": None,
                "extent":            {"east_west": 0, "north_south": 0},
                "distance_unit":     unit.value,
            })

        terrain_types  = sorted({c["system_terrain"] for c in cells if c.get("system_terrain")})
        materials      = sorted({c["cell_material"]   for c in cells if c.get("cell_material")})
        has_structural = any(c.get("is_structural") for c in cells)
        danger_levels  = sorted({c["danger_level_override"] for c in cells if c.get("danger_level_override")})

        modifiers = [c["travel_modifier_override"] for c in cells if c.get("travel_modifier_override") is not None]
        travel_difficulty = round(sum(modifiers) / len(modifiers), 2) if modifiers else None

        xs = [c["x"] for c in cells]
        ys = [c["y"] for c in cells]
        extent = {
            "east_west":   round((max(xs) - min(xs)) * factor) if xs else 0,
            "north_south": round((max(ys) - min(ys)) * factor) if ys else 0,
        }

        logger.info(
            "terrain_summary | location=%s terrain_types=%s materials=%s cells=%d unit=%s",
            location_uid, terrain_types, materials, len(cells), unit.value,
        )

        # TODO: добавить has_road / road_types из road_repo когда будет ТЗ по дорогам
        return NodeResult(data={
            "location_uid":      location_uid,
            "terrain_types":     terrain_types,
            "materials":         materials,
            "has_structural":    has_structural,
            "danger_levels":     danger_levels,
            "travel_difficulty": travel_difficulty,
            "extent":            extent,
            "distance_unit":     unit.value,
        })