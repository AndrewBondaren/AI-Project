import logging
from dataclasses import dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType

logger = logging.getLogger(__name__)


class TerrainLocationMissingError(PythonNodeError):
    """location_uid из сцены не найден в DB — битые данные."""
    code = "terrain_location_missing"
    requires_replan = False
    user_message = "Локация не найдена. Данные сессии повреждены."


class TerrainLocationNoCoordinatesError(PythonNodeError):
    """У локации нет map_x/y/z — lazy-генерация невозможна."""
    code = "terrain_location_no_coordinates"
    requires_replan = False
    user_message = "У локации не заданы координаты на карте мира."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class CheckTerrainNode(PythonNode):
    """
    Читает сцену из shared_context["scene"], загружает NamedLocation,
    проверяет наличие MapCells в DB.
    skip_on_replan=False — читает DB на каждом pass.
    """

    id:   str = "check_terrain"
    name: str = "Check Terrain"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = False

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["check_scene"])
    possible_errors: list = field(default_factory=lambda: [
        TerrainLocationMissingError,
        TerrainLocationNoCoordinatesError,
    ])

    async def execute(self, state, context) -> NodeResult:
        scene        = state.shared_context["scene"]
        location_uid = scene.location_uid
        world_uid    = state.session.meta.get("world_uid")

        location = await context["location_repo"].get_by_id(location_uid)
        if location is None:
            raise TerrainLocationMissingError(
                f"Location '{location_uid}' not found for terrain check"
            )

        if location.map_x is None or location.map_y is None or location.map_z is None:
            raise TerrainLocationNoCoordinatesError(
                f"Location '{location_uid}' has no map coordinates"
            )

        has_terrain = await context["map_cell_repo"].has_cells_for_location(location_uid)

        logger.info(
            "check_terrain | session=%s location=%s map=(%d,%d,%d) has_terrain=%s",
            state.session.session_id, location_uid,
            location.map_x, location.map_y, location.map_z, has_terrain,
        )

        return NodeResult(data={
            "has_terrain":   has_terrain,
            "location_uid":  location_uid,
            "location_name": location.display_name,
            "map_x":         location.map_x,
            "map_y":         location.map_y,
            "map_z":         location.map_z,
            "world_uid":     world_uid,
        })
