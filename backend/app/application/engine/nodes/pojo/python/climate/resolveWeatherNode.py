import logging
from dataclasses import dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.application.worldData.generators.assemblers.climateAssembler.climateRuntimeAssembler import (
    ClimateRuntimeAssembler,
)

logger = logging.getLogger(__name__)

_runtime = ClimateRuntimeAssembler()


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class ResolveWeatherNode(PythonNode):
    """Runtime weather snapshot from scene cell climate fields (pre_llm)."""

    id:   str = "resolve_weather"
    name: str = "Resolve Weather"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["terrain_context"])
    possible_errors: list = field(default_factory=list)

    async def execute(self, state, context) -> NodeResult:
        terrain = state.shared_context.get("terrain", {})
        cells   = terrain.get("cells", [])
        world_uid = state.session.meta.get("world_uid")
        world   = await context["world_repo"].get_by_id(world_uid)

        temp     = 12
        rainfall = 0
        if cells:
            temps = [c.get("temperature_base") for c in cells if c.get("temperature_base") is not None]
            rains = [c.get("rainfall") for c in cells if c.get("rainfall") is not None]
            if temps:
                temp = int(sum(temps) / len(temps))
            if rains:
                rainfall = int(sum(rains) / len(rains))

        season = None
        snapshot = _runtime.resolve_weather(world, temp, rainfall, season)
        state.shared_context["weather"] = {
            "season":                snapshot.season,
            "temperature_base":      snapshot.temperature_base,
            "effective_temperature": snapshot.effective_temperature,
            "rainfall":              snapshot.rainfall,
            "system_weather":        snapshot.system_weather,
            "intensity":             snapshot.intensity,
        }

        logger.info(
            "resolve_weather | world=%s effective_temp=%d rainfall=%d",
            world_uid, snapshot.effective_temperature, snapshot.rainfall,
        )
        return NodeResult(data=state.shared_context["weather"])
