import logging
from dataclasses import asdict, dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)

logger = logging.getLogger(__name__)

_SETTLEMENT_TYPES = frozenset({"city", "town", "village", "camp", "hamlet"})

_generator = SettlementGeneratorService()


class LazySettlementWorldMissingError(PythonNodeError):
    code = "lazy_settlement_world_missing"
    requires_replan = False
    user_message = "Мир не найден. Данные сессии повреждены."


class LazySettlementGenerationError(PythonNodeError):
    code = "lazy_settlement_generation_failed"
    requires_replan = False
    user_message = "Не удалось сгенерировать поселение."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class LazySettlementNode(PythonNode):
    """
    Lazy phase 2 (tz_city_generation.md): полная геометрия поселения при первом входе.
    Noop если тип не settlement или building cells уже есть в footprint.
    """

    id:   str = "lazy_settlement"
    name: str = "Lazy Settlement Generate"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["check_terrain", "lazy_terrain"])
    possible_errors: list = field(default_factory=lambda: [
        LazySettlementWorldMissingError,
        LazySettlementGenerationError,
    ])

    async def execute(self, state, context) -> NodeResult:
        check = state.node_results["check_terrain"]

        location = await context["location_repo"].get_by_id(check["location_uid"])
        if location is None:
            raise LazySettlementGenerationError(
                f"Location '{check['location_uid']}' not found"
            )

        if location.system_location_type not in _SETTLEMENT_TYPES:
            return NodeResult(data={"cells": [], "skipped": True, "reason": "not_settlement"})

        world = await context["world_repo"].get_by_id(check["world_uid"])
        if world is None:
            raise LazySettlementWorldMissingError(
                f"World '{check['world_uid']}' not found"
            )

        existing = await context["map_cell_repo"].get_by_world(check["world_uid"])
        if not _generator.needs_geometry(location, world, existing):
            logger.debug(
                "lazy_settlement | skipped — geometry exists for location=%s",
                check["location_uid"],
            )
            return NodeResult(data={"cells": [], "skipped": True, "reason": "already_generated"})

        terrain_cells = [
            c for c in existing
            if c.location_uid == location.location_uid
        ] or None

        try:
            _, cells = _generator.generate_map_cells(world, location, terrain_cells)
        except Exception as exc:
            raise LazySettlementGenerationError(
                f"Settlement generation failed for '{location.location_uid}': {exc}"
            ) from exc

        if not cells:
            raise LazySettlementGenerationError(
                f"generate_map_cells returned empty for '{location.location_uid}'"
            )

        inserted = await context["map_cell_repo"].insert_bulk_ignore(cells)

        logger.info(
            "lazy_settlement | location=%s cells=%d inserted=%d",
            location.location_uid,
            len(cells),
            inserted,
        )

        return NodeResult(data={
            "cells":    [asdict(c) for c in cells],
            "skipped":  False,
            "inserted": inserted,
        })
