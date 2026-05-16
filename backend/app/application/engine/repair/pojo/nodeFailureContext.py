from dataclasses import dataclass


@dataclass
class NodeFailureContext:
    node_id: str
    dsl_task: str
    error_codes: list[str]
    output: dict | None