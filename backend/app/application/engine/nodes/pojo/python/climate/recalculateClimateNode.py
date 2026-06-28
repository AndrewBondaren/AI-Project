import logging
from dataclasses import asdict, dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService
from app.application.worldData.generators.assemblers.climateAssembler.types import ClimateRecalcRequest

logger = logging.getLogger(__name__)

_orchestrator = ClimateOrchestratorService()


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class RecalculateClimateNode(PythonNode):
    """Partial climate update on existing heightmap (post_llm)."""

    id:   str = "recalculate_climate"
    name: str = "Recalculate Climate"

    phase:          Literal["pre_llm", "post_llm"] = "post_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=list)
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=list)
    possible_errors: list = field(default_factory=list)

    async def execute(self, state, context) -> NodeResult:
        world_uid = state.session.meta.get("world_uid")
        world     = await context["world_repo"].get_by_id(world_uid)
        locations = await context["location_repo"].get_by_world(world_uid)
        cells     = await context["map_cell_repo"].get_by_world(world_uid)

        request = ClimateRecalcRequest()
        updated = _orchestrator.recalculate(world, locations, cells, request)
        if updated:
            await context["map_cell_repo"].upsert_climate_fields(updated)

        logger.info(
            "recalculate_climate | world=%s cells=%d",
            world_uid, len(updated),
        )
        return NodeResult(data={"cells": [asdict(c) for c in updated], "count": len(updated)})
