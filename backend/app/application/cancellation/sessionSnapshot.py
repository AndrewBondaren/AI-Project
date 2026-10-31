# TODO(B2/B2-L32): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.cancellation.typed.sessionSnapshot.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass


@dataclass
class SessionSnapshot:
    session_id: str
    node_results: dict
    node_status: dict
    task_type: str
    original_message: str
