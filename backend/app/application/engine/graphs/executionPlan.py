from dataclasses import dataclass


@dataclass
class ExecutionPlan:

    levels: list[list[str]]
    priority_sorted: list[str]
    estimated_cost: float