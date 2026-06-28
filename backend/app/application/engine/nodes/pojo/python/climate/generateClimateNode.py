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
from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService

logger = logging.getLogger(__name__)

_orchestrator = ClimateOrchestratorService()


class GenerateClimateEmptyMapError(PythonNodeError):
    code = "generate_climate_empty_map"
    requires_replan = False
    user_message = "Нет ячеек карты — сначала generate-surface."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class GenerateClimateNode(PythonNode):
    """Climate materialization pass on existing map_cells (post_llm)."""

    id:   str = "generate_climate"
    name: str = "Generate Climate"

    phase:          Literal["pre_llm", "post_llm"] = "post_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=list)
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=list)
    possible_errors: list = field(default_factory=lambda: [GenerateClimateEmptyMapError])

    async def execute(self, state, context) -> NodeResult:
        world_uid = state.session.meta.get("world_uid")
        world     = await context["world_repo"].get_by_id(world_uid)
        locations = await context["location_repo"].get_by_world(world_uid)
        cells     = await context["map_cell_repo"].get_by_world(world_uid)

        if not cells:
            raise GenerateClimateEmptyMapError(
                f"No map cells for world '{world_uid}'"
            )

        climate_cells = _orchestrator.apply_climate_pass(world, locations, cells)
        await context["map_cell_repo"].upsert_climate_fields(climate_cells)

        logger.info(
            "generate_climate | world=%s cells=%d",
            world_uid, len(climate_cells),
        )
        return NodeResult(data={"cells": [asdict(c) for c in climate_cells], "count": len(climate_cells)})
