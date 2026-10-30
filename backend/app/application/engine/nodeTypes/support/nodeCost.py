from dataclasses import dataclass


@dataclass(frozen=True)
class NodeCost:

    cpu: float = 1.0
    llm_calls: int = 1
    latency_ms: int = 100