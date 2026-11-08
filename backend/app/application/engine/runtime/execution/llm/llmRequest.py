"""Integration binds a provider/model; runtime owns conversation ordering only."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.application.engine.repair.repairMode import RepairMode
from app.application.llm.models import ChatMessage
from app.dataModel.engine.dag.diagnostics import Index


class LLMRequest(Protocol):
    async def __call__(
        self, messages: list[ChatMessage], schema: dict[str, object], *, enable_thinking: bool, temperature: float,
    ) -> str: ...


class LLMOptionFields(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True, frozen=True)

    player_message: str
    language: str
    system_role: bool
    repair_iterations: Index
    repair_mode: RepairMode


@dataclass(frozen=True, kw_only=True)
class LLMExecutionOptions:
    player_message: str
    language: str
    repair_iterations: Index
    repair_mode: RepairMode
    system_role: bool = False

    def __post_init__(self) -> None:
        LLMOptionFields.model_validate(self)
