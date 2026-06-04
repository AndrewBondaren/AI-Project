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
# Ошибки
# ---------------------------------------------------------------------------

class InvalidLocationError(PythonNodeError):
    code = "invalid_location"
    requires_replan = False
    user_message = "Локация не найдена. Попробуйте выбрать снова."


class NoAvailableChildrenError(PythonNodeError):
    code = "no_available_children"
    requires_replan = False
    user_message = "Все помещения здесь заняты. Попробуйте выбрать другое место."


class LocationNotAccessibleError(PythonNodeError):
    code = "location_not_accessible"
    requires_replan = False
    user_message = "Эта локация не является конечной точкой размещения. Выберите конкретное место внутри."


# ---------------------------------------------------------------------------
# Общая проверка доступности локации для игрока (используется в обеих нодах)
# ---------------------------------------------------------------------------

def _resolve_type_display(location_type: str, registry: dict) -> str | None:
    entry = registry.get(location_type)
    if not entry:
        return None
    return entry.get("display_name") if isinstance(entry, dict) else str(entry)


def can_start(location, player_uid, player_faction_uid, faction_access_list, npc_home_occupied_uids):
    """
    Возвращает True если игрок может начать сцену в данной локации.

    faction_access_list: [(faction_uid, is_allowed), ...] из location_faction_access
    npc_home_occupied_uids: set uid локаций занятых NPC-резидентами
    """
    if location.is_forbidden:
        # allowlist mode: пускаем только явно разрешённые фракции + владельца
        allowed = {fa[0] for fa in faction_access_list if fa[1]}
        if player_faction_uid not in allowed and location.owner_uid != player_uid:
            return False
    else:
        # denylist mode: блокируем явно запрещённые фракции
        banned = {fa[0] for fa in faction_access_list if not fa[1]}
        if player_faction_uid in banned:
            return False

    if not location.is_public:
        if location.location_uid in npc_home_occupied_uids:
            return False

    return True


# ---------------------------------------------------------------------------
# Node 1: валидация + дочерние локации
# ---------------------------------------------------------------------------

@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class SceneLocationChildrenNode(PythonNode):
    """
    Валидирует выбранную локацию и возвращает список доступных дочерних.
    Фильтр: is_accessible + faction-aware can_start.
    children: [] означает leaf — здание/комната без подразделений.
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
        character_id = state.session.meta.get("character_id")

        world    = await context["world_repo"].get_by_id(world_uid)
        type_registry = world.location_type_registry if world else {}

        location = await context["location_repo"].get_by_id(location_uid)
        if location is None or location.world_uid != world_uid:
            raise InvalidLocationError(
                f"Location '{location_uid}' not found or does not belong to world '{world_uid}'"
            )

        children = await context["location_repo"].get_children(location_uid)
        children = [c for c in children if c.is_selectable]

        available = children
        if children:
            player = await context["player_repo"].get_by_id(character_id) if character_id else None
            player_uid         = player.character_uid if player else None
            player_faction_uid = player.system_faction_uid if player else None

            child_uids         = [c.location_uid for c in children]
            faction_access_map = await context["location_repo"].get_faction_access_bulk(child_uids)
            occupied_uids      = await context["npc_repo"].get_home_occupied_uids(world_uid, child_uids)

            available = [
                c for c in children
                if can_start(
                    c, player_uid, player_faction_uid,
                    faction_access_map.get(c.location_uid, []),
                    occupied_uids,
                )
            ]

            if not available:
                raise NoAvailableChildrenError(
                    f"All {len(children)} children of '{location_uid}' are blocked (faction/NPC)"
                )

        # Batch fetch государств для дочерних локаций
        state_uids = list({c.state_uid for c in available if c.state_uid})
        states_map: dict[str, str] = {}
        if state_uids:
            fetched = await context["state_repo"].get_by_uids(state_uids)
            states_map = {s.state_uid: s.display_name for s in fetched}

        logger.info(
            "scene_location_children | uid=%s children_total=%d available=%d",
            location_uid, len(children), len(available),
        )

        return NodeResult(data={
            "location_uid":         location.location_uid,
            "location_name":        location.display_name,
            "location_description": location.display_description or "",
            "is_accessible":        location.is_accessible,
            "children": [
                {
                    "uid":          c.location_uid,
                    "name":         c.display_name,
                    "type_display": _resolve_type_display(c.system_location_type, type_registry),
                    "state_name":   states_map.get(c.state_uid) if c.state_uid else None,
                }
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
    possible_errors: list = field(default_factory=lambda: [LocationNotAccessibleError])

    async def execute(self, state, context) -> NodeResult:
        data          = state.node_results["scene_location_children"]
        location_uid  = data["location_uid"]
        location_name = data["location_name"]
        children      = data["children"]

        if children:
            return NodeResult(data={
                "type": "select_child",
                "parent": {"uid": location_uid, "name": location_name},
                "children": children,
            })

        if not data.get("is_accessible", True):
            raise LocationNotAccessibleError(
                f"Location '{location_uid}' is not accessible and has no selectable children"
            )

        now = datetime.now(timezone.utc).isoformat()
        scene = SessionScene(
            session_id=state.session.session_id,
            location_uid=location_uid,
            level_uid=None,  # заполняется когда location_levels реализованы
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
