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

class NoLocationsAvailableError(PythonNodeError):
    """В мире нет ни одной доступной локации нужного уровня."""
    code = "no_locations_available"
    requires_replan = False
    user_message = "В мире нет доступных локаций."


# ---------------------------------------------------------------------------
# Вспомогательная функция: глубина в иерархии (in-memory)
# ---------------------------------------------------------------------------

def _build_depth_map(all_locations) -> dict[str, int]:
    """
    Строит карту uid → глубина на основе parent_location_uid.
    Корневые локации (parent IS NULL) имеют глубину 0.
    Работает in-memory без дополнительных запросов к БД.
    """
    parent_map = {loc.location_uid: loc.parent_location_uid for loc in all_locations}
    memo: dict[str, int] = {}

    def depth(uid: str) -> int:
        if uid in memo:
            return memo[uid]
        parent = parent_map.get(uid)
        result = 0 if parent is None else 1 + depth(parent)
        memo[uid] = result
        return result

    for loc in all_locations:
        depth(loc.location_uid)

    return memo


# ---------------------------------------------------------------------------
# Нода
# ---------------------------------------------------------------------------

@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class SceneInitNode(PythonNode):
    id:   str = "scene_init"
    name: str = "Scene Init"

    phase: Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [TaskType.SCENE_INIT])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=list)
    possible_errors: list = field(default_factory=lambda: [NoLocationsAvailableError])

    async def execute(self, state, context) -> NodeResult:
        world_uid    = state.session.meta.get("world_uid")
        character_id = state.session.meta.get("character_id")

        all_locations = await context["location_repo"].get_by_world(world_uid)
        if not all_locations:
            raise NoLocationsAvailableError(
                f"No locations found for world '{world_uid}'"
            )

        uid_to_loc = {loc.location_uid: loc for loc in all_locations}

        # ------------------------------------------------------------------
        # Родная локация персонажа.
        # system_location — FK (location_uid). display_location — только для UI.
        # ------------------------------------------------------------------
        home_uid = None
        if character_id:
            player = await context["player_repo"].get_by_id(character_id)
            if player and player.system_location and player.system_location in uid_to_loc:
                home_uid = player.system_location

        # ------------------------------------------------------------------
        # Фильтрация по уровню иерархии.
        #
        # Иерархия (ТЗ): region(0) → territory(1) → settlement(2) → district(3) → room(4)
        # N+1: пользователь добавляет свои типы на любом уровне.
        #
        # Стратегия (без world_repo, только по данным из named_locations):
        #   • Знаем home_uid → вычисляем его глубину → показываем ВСЕ локации
        #     той же глубины (все settlements, не только типа home).
        #   • Не знаем home → исключаем корень (depth=0, регионы).
        # ------------------------------------------------------------------
        depth_map = _build_depth_map(all_locations)

        if home_uid:
            target_depth = depth_map[home_uid]
            locations = [
                l for l in all_locations
                if depth_map[l.location_uid] == target_depth and l.is_accessible
            ]
        else:
            locations = [
                l for l in all_locations
                if depth_map[l.location_uid] > 0 and l.is_accessible
            ]

        if not locations:
            raise NoLocationsAvailableError(
                f"No accessible locations at suitable hierarchy level for world '{world_uid}'"
            )

        # Сортируем: home первым, остальные по алфавиту
        sorted_locations = sorted(
            locations,
            key=lambda l: (0 if l.location_uid == home_uid else 1, l.display_name),
        )

        logger.info(
            "scene_init locations_count=%d home_uid=%s target_depth=%s",
            len(sorted_locations),
            home_uid,
            depth_map.get(home_uid, "?") if home_uid else "unknown",
        )

        return NodeResult(data={
            "type":     "select_child",
            "parent":   None,
            "children": [
                {
                    "uid":     loc.location_uid,
                    "name":    loc.display_name,
                    "is_home": loc.location_uid == home_uid,
                }
                for loc in sorted_locations
            ],
        })
