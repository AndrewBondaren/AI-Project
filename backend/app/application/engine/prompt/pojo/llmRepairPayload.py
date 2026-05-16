from dataclasses import dataclass

from app.application.engine.prompt.pojo.llmPayload import LLMPayload


@dataclass
class LLMRepairPayload(LLMPayload):
    errors: dict[str, list[str]]  # node_id → [error_codes]

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload["type"] = "repair"
        payload["errors"] = self.errors
        return payload