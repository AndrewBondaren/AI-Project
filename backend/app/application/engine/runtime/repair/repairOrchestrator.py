"""Bounded repair in the initial conversation; no publication or domain policy."""

import asyncio
from collections.abc import Callable
import json

from pydantic import BaseModel

from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.nodeOutcome import NodeOutcome
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.llm.models import ChatMessage
from app.dataModel.engine.dag.errors.nodeError import NodeError

type GroupValidation = tuple[tuple[NodeOutcome[BaseModel, NodeError], ...], tuple[NodeFailureContext[BaseModel], ...]]


def cancellation_checkpoint() -> None:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError


class RepairOrchestrator:
    def __init__(self, builder: RepairBuilder) -> None:
        self._builder = builder

    async def repair(
        self, base: LLMPayload, validation: GroupValidation, messages: list[ChatMessage],
        request: LLMRequest, validate: Callable[[str, int], GroupValidation], *,
        options: LLMExecutionOptions, enable_thinking: bool, temperature: float,
    ) -> tuple[NodeOutcome[BaseModel, NodeError], ...]:
        outcomes, failures = validation
        for attempt in range(1, options.repair_iterations + 1):
            cancellation_checkpoint()
            if not failures or any(not failure.validation.retryable for failure in failures):
                break
            payload = self._builder.build(base, failures, mode=options.repair_mode)
            wire = payload.to_user_dict() if options.system_role else payload.to_dict()
            messages.append(ChatMessage(role="user", content=json.dumps(wire, ensure_ascii=False)))
            raw = await request(messages, payload.response_format_schema, enable_thinking=enable_thinking, temperature=temperature)
            cancellation_checkpoint()
            messages.append(ChatMessage(role="assistant", content=raw))
            outcomes, failures = validate(raw, attempt)
        return outcomes
