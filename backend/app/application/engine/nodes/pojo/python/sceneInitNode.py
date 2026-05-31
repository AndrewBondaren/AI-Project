import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.nodes.pojo.python.sceneLocationSelectNode import can_start
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.db.models.sessionScene import SessionScene

logger = logging.getLogger(__name__)


class NoLocationsAvailableError(PythonNodeError):
    """В мире нет ни одной доступной локации нужного уровня."""
    code = "no_locations_available"
    requires_replan = False
    user_message = "В мире нет доступных локаций."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class SceneInitNode(PythonNode):
    id:   str = "scene_init"
    name: str = "Scene Init"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
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
            raise NoLocationsAvailableError(f"No locations found for world '{world_uid}'")

        uid_to_loc = {loc.location_uid: loc for loc in all_locations}

        player = None
        home_uid            = None
        home_settlement_uid = None
        if character_id:
            player = await context["player_repo"].get_by_id(character_id)
            if player:
                if player.system_home_location_uid and player.system_home_location_uid in uid_to_loc:
                    home_uid = player.system_home_location_uid
                if player.system_home_settlement_uid and player.system_home_settlement_uid in uid_to_loc:
                    home_settlement_uid = player.system_home_settlement_uid

        # Глубина через WITH RECURSIVE CTE — всегда точна, нет проблемы синхронизации
        depth_map = await context["location_repo"].get_tree(world_uid)

        if home_uid:
            target_depth = depth_map.get(home_uid)
        elif home_settlement_uid:
            settlement_depth = depth_map.get(home_settlement_uid)
            target_depth = (settlement_depth + 1) if settlement_depth is not None else None
        else:
            target_depth = None

        if target_depth is not None:
            candidates = [
                l for l in all_locations
                if depth_map.get(l.location_uid) == target_depth and l.is_accessible
            ]
        else:
            non_root = [l for l in all_locations if depth_map.get(l.location_uid, 0) > 0]
            if non_root:
                min_depth = min(depth_map[l.location_uid] for l in non_root)
                candidates = [
                    l for l in non_root
                    if depth_map.get(l.location_uid) == min_depth and l.is_accessible
                ]
            else:
                candidates = []

        # Faction-aware фильтр (тот же can_start что в SceneLocationChildrenNode)
        player_uid         = player.character_uid if player else None
        player_faction_uid = player.system_faction_uid if player else None

        candidate_uids     = [l.location_uid for l in candidates]
        faction_access_map = await context["location_repo"].get_faction_access_bulk(candidate_uids)
        occupied_uids      = await context["npc_repo"].get_home_occupied_uids(world_uid, candidate_uids)

        locations = [
            l for l in candidates
            if can_start(
                l, player_uid, player_faction_uid,
                faction_access_map.get(l.location_uid, []),
                occupied_uids,
            )
        ]

        if not locations:
            raise NoLocationsAvailableError(
                f"No accessible locations at suitable depth for world '{world_uid}'"
            )

        sorted_locations = sorted(
            locations,
            key=lambda l: (0 if l.location_uid == home_uid else 1, l.display_name),
        )

        logger.info(
            "scene_init | locations=%d home_uid=%s target_depth=%s",
            len(sorted_locations), home_uid, target_depth,
        )

        now = datetime.now(timezone.utc).isoformat()
        await context["scene_repo"].upsert(SessionScene(
            session_id=state.session.session_id,
            location_uid=None,
            level_uid=None,
            description="",
            actors=[],
            created_at=now,
            updated_at=now,
        ))

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
