"""Integration binds a provider/model; runtime owns conversation ordering only."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import TypeAdapter

from app.application.engine.repair.repairMode import RepairMode
from app.application.llm.models import ChatMessage
from app.dataModel.engine.dag.diagnostics import Index


class LLMRequest(Protocol):
    async def __call__(
        self, messages: list[ChatMessage], schema: dict[str, object], *, enable_thinking: bool, temperature: float,
    ) -> str: ...


@dataclass(frozen=True, kw_only=True)
class LLMExecutionOptions:
    player_message: str
    language: str
    repair_iterations: Index
    repair_mode: RepairMode
    system_role: bool = False

    def __post_init__(self) -> None:
        TypeAdapter(str).validate_python(self.player_message, strict=True)
        TypeAdapter(str).validate_python(self.language, strict=True)
        TypeAdapter(bool).validate_python(self.system_role, strict=True)
        TypeAdapter(Index).validate_python(self.repair_iterations, strict=True)
        TypeAdapter(RepairMode).validate_python(self.repair_mode, strict=True)
