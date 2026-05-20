from dataclasses import dataclass

from app.application.engine.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.repair.pojo.nodeFailureContext import NodeFailureContext


@dataclass
class LLMRepairPayload(LLMPayload):
    errors: list[NodeFailureContext]

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload["type"] = "repair"
        payload["errors"] = [
            {
                "node_id":     e.node_id,
                "dsl_task":    e.dsl_task,
                "error_codes": e.error_codes,
                "output":      e.output,
            }
            for e in self.errors
        ]
        return payload
