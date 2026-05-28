import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.db.models.sessionScene import SessionScene

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Объявленные ошибки
# ---------------------------------------------------------------------------

class InvalidLocationError(PythonNodeError):
    code = "invalid_location"
    requires_replan = False
    user_message = "Локация не найдена. Попробуйте выбрать снова."


class NoAvailableChildrenError(PythonNodeError):
    code = "no_available_children"
    requires_replan = False
    user_message = "Все помещения здесь заняты. Попробуйте выбрать другое место."


# ---------------------------------------------------------------------------
# Node 1: валидация + дочерние локации
# ---------------------------------------------------------------------------

@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class SceneLocationChildrenNode(PythonNode):
    """
    Валидирует выбранную локацию и возвращает список доступных дочерних.
    Фильтрует здания/помещения с NPC-резидентами (home_location_uid).
    children: [] означает leaf-ноду — здание без подразделений.
    """

    id:   str = "scene_location_children"
    name: str = "Scene Location Children"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [TaskType.SCENE_START_LOCATION_SELECT])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=list)
    possible_errors: list = field(default_factory=lambda: [
        InvalidLocationError,
        NoAvailableChildrenError,
    ])

    async def execute(self, state, context) -> NodeResult:
        location_uid = state.message.strip()
        world_uid    = state.session.meta.get("world_uid")

        location = await context["location_repo"].get_by_id(location_uid)
        if location is None or location.world_uid != world_uid:
            raise InvalidLocationError(
                f"Location '{location_uid}' not found or does not belong to world '{world_uid}'"
            )

        children = await context["location_repo"].get_children(location_uid)
        children = [c for c in children if c.is_accessible]

        available = children
        if children:
            child_uids    = [c.location_uid for c in children]
            occupied_uids = await context["npc_repo"].get_home_occupied_uids(world_uid, child_uids)
            available     = [c for c in children if c.location_uid not in occupied_uids]

            if not available:
                raise NoAvailableChildrenError(
                    f"All {len(children)} children of '{location_uid}' are NPC-occupied"
                )

        logger.info(
            "scene_location_children | uid=%s children_total=%d available=%d",
            location_uid, len(children), len(available),
        )

        return NodeResult(data={
            "location_uid":         location.location_uid,
            "location_name":        location.display_name,
            "location_description": location.display_description or location.system_description or "",
            "children": [
                {"uid": c.location_uid, "name": c.display_name}
                for c in available
            ],
        })


# ---------------------------------------------------------------------------
# Node 2: финальный ответ — drill-down или создание сцены
# ---------------------------------------------------------------------------

@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class SceneStartLocationSelectNode(PythonNode):
    """
    Читает результат SceneLocationChildrenNode.
    Если children непустые — возвращает их (следующий шаг выбора).
    Если children пустые (leaf) — создаёт session_scene.
    """

    id:   str = "scene_start_location_select"
    name: str = "Scene Location Select"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [TaskType.SCENE_START_LOCATION_SELECT])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["scene_location_children"])
    possible_errors: list = field(default_factory=list)

    async def execute(self, state, context) -> NodeResult:
        data         = state.node_results["scene_location_children"]
        location_uid = data["location_uid"]
        location_name = data["location_name"]
        children     = data["children"]

        if children:
            return NodeResult(data={
                "type": "select_child",
                "parent": {
                    "uid":  location_uid,
                    "name": location_name,
                },
                "children": children,
            })

        now = datetime.now(timezone.utc).isoformat()
        scene = SessionScene(
            session_id=state.session.session_id,
            location_uid=location_uid,
            description=data["location_description"],
            actors=[],
            created_at=now,
            updated_at=now,
        )
        await context["scene_repo"].upsert(scene)

        logger.info(
            "scene_created | session_id=%s location=%s uid=%s",
            state.session.session_id, location_name, location_uid,
        )

        return NodeResult(data={
            "type": "scene_ready",
            "location": {
                "uid":         location_uid,
                "name":        location_name,
                "description": scene.description,
            },
        })
