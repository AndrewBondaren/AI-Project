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


# ---------------------------------------------------------------------------
# Объявленные ошибки ноды
# ---------------------------------------------------------------------------

class SceneNotFoundError(PythonNodeError):
    """Запись session_scene отсутствует — сцена не инициализирована."""
    code = "scene_not_found"
    requires_replan = True
    next_task_type = TaskType.SCENE_INIT
    user_message = "Сцена не инициализирована."


class SceneLocationSelectPendingError(PythonNodeError):
    """session_scene существует, но location_uid не задан — идёт выбор локации."""
    code = "scene_location_select_pending"
    requires_replan = True
    next_task_type = TaskType.SCENE_START_LOCATION_SELECT
    user_message = "Выберите локацию для начала игры."


class LocationNotFoundError(PythonNodeError):
    """location_uid в сцене указывает на несуществующую локацию — битые данные."""
    code = "location_not_found"
    requires_replan = False  # фатальная: данные в БД некорректны
    user_message = "Локация не найдена. Данные сессии повреждены."


# ---------------------------------------------------------------------------
# Нода
# ---------------------------------------------------------------------------

@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class CheckSceneNode(PythonNode):
    id:   str = "check_scene"
    name: str = "Check Scene"

    skip_on_replan: bool = False  # читает из БД — перезапускать на каждом pass
    phase: Literal["pre_llm", "post_llm"] = "pre_llm"

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.INTENT_DETECTION,
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
        TaskType.LOCAL_REGION_ANALYSIS,
    ])
    rules:          list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:           list = field(default_factory=list)
    possible_errors: list = field(default_factory=lambda: [
        SceneNotFoundError,
        SceneLocationSelectPendingError,
        LocationNotFoundError,
    ])

    async def execute(self, state, context) -> NodeResult:
        logger.debug(
            "check_scene called | pass=%s task_type=%s session_id=%s",
            state.pass_number, state.task_type, state.session.session_id,
        )

        scene = await context["scene_repo"].get(state.session.session_id)
        if scene is None:
            raise SceneNotFoundError(f"No scene for session '{state.session.session_id}'")
        if scene.location_uid is None:
            raise SceneLocationSelectPendingError(
                f"Session '{state.session.session_id}' has draft scene — location selection pending"
            )

        state.shared_context["scene"] = scene

        location_name = None
        if scene.location_uid:
            location = await context["location_repo"].get_by_id(scene.location_uid)
            if location is None:
                raise LocationNotFoundError(
                    f"Location '{scene.location_uid}' not found (session '{scene.session_id}')"
                )
            location_name = location.display_name

        return NodeResult(data={
            "location":    location_name,
            "description": scene.description,
            "actors":      scene.actors,
        })
