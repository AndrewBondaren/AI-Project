#from dataclasses import dataclass, field
#from app.application.engine.nodes.pojo.compiledNode import CompiledNode


#@dataclass
#class ExecutionPlan:
#    levels: list[list[str]]                  # уровни node_id
#    nodes: dict[str, CompiledNode]           # node_id → CompiledNode
#    priority_sorted: list[str]               # все node_id по приоритету
#    estimated_cost: float = 0.0