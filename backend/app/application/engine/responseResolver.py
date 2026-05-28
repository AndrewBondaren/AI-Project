import logging
from dataclasses import dataclass
from typing import Any

from app.application.engine.taskType import TaskType

logger = logging.getLogger(__name__)


@dataclass
class ResolveResult:
    ok: bool
    data: Any = None            # output ноды — когда ok=True
    error: str | None = None    # user-facing сообщение — когда ok=False


class ResponseResolver:
    """
    Извлекает user-facing ответ из state.node_results по итоговому task_type.

    Политика:
      1. Если для task_type зарегистрирована выходная нода и она произвела output
         → ok=True, data=output
      2. Если output нет, но state.user_error выставлен gate-нодой
         → ok=False, error=user_error   (задекларированное сообщение из PythonNodeError)
      3. Иначе → ok=False, error=<технический fallback>

    Новый task_type регистрируется добавлением одной строки в _OUTPUT_NODE.
    """

    _OUTPUT_NODE: dict[TaskType, str] = {
        TaskType.SCENE_NARRATION:           "scene_narration",
        TaskType.SCENE_COMBAT:              "scene_combat",
        TaskType.SCENE_CHANGE_LOCATION:     "scene_change_location",
        TaskType.SCENE_INIT:                "scene_init",
        TaskType.SCENE_START_LOCATION_SELECT:     "scene_start_location_select",
        TaskType.LOCAL_SCENE_ANALYSIS:      "local_scene_analysis",
        TaskType.LOCAL_REGION_ANALYSIS:     "local_region_analysis",
    }

    def resolve(self, state) -> ResolveResult:
        node_id = self._OUTPUT_NODE.get(state.task_type)

        if node_id is not None:
            output = state.node_results.get(node_id)
            if output is not None:
                logger.debug(
                    "response_resolved task_type=%s node_id=%s",
                    state.task_type, node_id,
                )
                return ResolveResult(ok=True, data=output)

            logger.warning(
                "response_missing task_type=%s expected_node=%s node_results=%s",
                state.task_type, node_id, list(state.node_results.keys()),
            )
        else:
            logger.warning(
                "response_unregistered task_type=%s", state.task_type,
            )

        if state.user_error:
            return ResolveResult(ok=False, error=state.user_error)

        return ResolveResult(
            ok=False,
            error=f"Задача '{state.task_type}' завершилась без результата.",
        )
