from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.engine.taskType import TaskType


class PythonNodeError(Exception):
    """
    Объявленная ошибка Python-ноды.

    Подклассы декларируют политику обработки через атрибуты класса:
      - code:            уникальный идентификатор ошибки
      - requires_replan: True  → движок прерывается, задача меняется на next_task_type
                         False → фатальная ошибка, запрос падает
      - next_task_type:  TaskType для перехода (только если requires_replan=True)
      - replan_reason:   человекочитаемая причина перехода (для логов)
      - user_message:    сообщение для пользователя; показывается если task_type
                         не произвёл output (gated) или запрос упал (fatal)
    """

    code: str = "python_node_error"
    requires_replan: bool = False
    next_task_type: TaskType | None = None
    replan_reason: str | None = None
    user_message: str | None = None
