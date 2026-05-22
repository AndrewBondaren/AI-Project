from dataclasses import dataclass, field
from app.application.engine.nodes.pojo.compiledNode import CompiledNode


@dataclass
class LLMGroup:
    """
    Одна temperature-группа LLM-нод.
    Все ноды группы выполняются как единый агрегированный LLM-вызов.
    """
    temperature: float
    levels: list[list[str]]          # топологические уровни внутри группы


@dataclass
class ExecutionPlan:
    """
    Результат компиляции DAG.

    Порядок выполнения:
      1. pre_llm_levels   — Python-ноды до LLM (asyncio.gather по уровням)
      2. llm_groups       — LLM-группы, отсортированные по temperature ASC;
                            каждая группа — один агрегированный вызов
      3. post_llm_levels  — Python-ноды после LLM (asyncio.gather по уровням)

    nodes — плоский словарь node_id -> CompiledNode для быстрого доступа.
    """
    pre_llm_levels:  list[list[str]]     # уровни Kahn внутри pre_llm фазы
    llm_groups:      list[LLMGroup]      # группы по temperature, ASC
    post_llm_levels: list[list[str]]     # уровни Kahn внутри post_llm фазы

    nodes:           dict[str, CompiledNode]
    estimated_cost:  float = 0.0