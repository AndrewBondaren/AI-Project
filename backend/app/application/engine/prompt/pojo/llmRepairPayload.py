# TODO(B2/B2-L25): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.prompt.pojo.llmRepairPayload.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass, field

from app.application.engine.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.repair.repairMode import RepairMode


@dataclass
class LLMRepairPayload(LLMPayload):
    errors: list[NodeFailureContext]
    mode: RepairMode = field(default=RepairMode.MAXIMUM)

    def to_dict(self) -> dict:
        errors_list = [
            {
                "node_id":     e.node_id,
                "dsl_task":    e.dsl_task,
                "error_codes": e.error_codes,
                "output":      e.output,
            }
            for e in self.errors
        ]

        if self.mode == RepairMode.ECONOMY:
            return {"type": "repair", "errors": errors_list}

        payload = super().to_dict()
        payload["type"] = "repair"
        payload["errors"] = errors_list
        return payload
