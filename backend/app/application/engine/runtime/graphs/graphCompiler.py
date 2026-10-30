"""Scheduling and contract checks only. SoT: node context §§6.1–6.2/8."""

from collections.abc import Callable, Sequence
from math import isfinite

from pydantic import BaseModel

from app.application.engine.contracts.executionBindings import ExecutionBindings
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.rules.rule import Rule
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan, LLMGroup
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, validate_python_phase
from app.dataModel.engine.dag.identity import NodeId

type RuleCompiler = Callable[
    [list[Rule]], Sequence[Callable[[BaseNode[BaseModel, BaseModel], object], bool]],
]
type RuleEvaluator = Callable[[CompiledNode[BaseModel, BaseModel], BaseModel], bool]


class GraphCompiler:
    def __init__(
        self, registry: NodeRegistry, bindings: ExecutionBindings, *,
        compile_rules: RuleCompiler, evaluate_rules: RuleEvaluator,
    ) -> None:
        self._registry = registry
        self._bindings = bindings
        self._compile_rules = compile_rules
        self._evaluate_rules = evaluate_rules
        self._nodes: dict[NodeId, CompiledNode[BaseModel, BaseModel]] | None = None
        self._registrations: dict[NodeId, NodeRegistration[BaseModel, BaseModel]] = {}

    def precompile(self) -> None:
        """Validate the full declared graph before applying conditional rules."""
        self._nodes = None
        registrations = {reg.node_id: reg for reg in self._registry.graph_registrations()}
        nodes: dict[NodeId, CompiledNode[BaseModel, BaseModel]] = {}
        for node_id, registration in registrations.items():
            node = registration.validate_node(self._bindings.make_node(registration))
            nodes[node_id] = CompiledNode(node, tuple(self._compile_rules(list(node.rules))))
        self._validate_graph(nodes, registrations)
        self._registrations = registrations
        self._nodes = nodes

    def compile(self, state: BaseModel) -> ExecutionPlan:
        if self._nodes is None:
            raise RuntimeError("GraphCompiler.precompile() must succeed before compile()")
        if tuple(self._registrations) != self._registry.ids():
            raise RuntimeError("registry changed; call GraphCompiler.precompile() again")
        selected = {
            node_id: compiled for node_id, compiled in self._nodes.items()
            if self._evaluate_rules(compiled, state)
        }
        pre: dict[NodeId, CompiledNode[BaseModel, BaseModel]] = {}
        post: dict[NodeId, CompiledNode[BaseModel, BaseModel]] = {}
        buckets: dict[float, dict[NodeId, CompiledNode[BaseModel, BaseModel]]] = {}
        for node_id, compiled in selected.items():
            phase = self._phase(compiled.node)
            if phase is ExecutionPhase.PRE_LLM:
                pre[node_id] = compiled
            elif phase is ExecutionPhase.POST_LLM:
                post[node_id] = compiled
            elif isinstance(compiled.node, LLMNode):
                buckets.setdefault(compiled.node.temperature, {})[node_id] = compiled
        return ExecutionPlan(
            pre_llm_levels=self._build_levels(pre),
            llm_groups=tuple(
                LLMGroup(temperature, self._build_levels(buckets[temperature]))
                for temperature in sorted(buckets)
            ),
            post_llm_levels=self._build_levels(post), nodes=selected,
            registrations={node_id: self._registrations[node_id] for node_id in selected},
            estimated_cost=sum(compiled.node.cost.cpu for compiled in selected.values()),
        )

    @staticmethod
    def _phase(node: BaseNode[BaseModel, BaseModel]) -> ExecutionPhase:
        if isinstance(node, PythonNode):
            return validate_python_phase(node.phase)
        if isinstance(node, LLMNode):
            if not isfinite(node.temperature):
                raise ValueError(f"node '{node.id}' has a non-finite LLM temperature")
            return ExecutionPhase.LLM
        raise TypeError(f"node '{node.id}' must be a PythonNode or LLMNode")

    @classmethod
    def _position(cls, node: BaseNode[BaseModel, BaseModel]) -> tuple[int, float]:
        phase = cls._phase(node)
        return tuple(ExecutionPhase).index(phase), node.temperature if isinstance(node, LLMNode) else 0.0

    @classmethod
    def _validate_graph(
        cls, nodes: dict[NodeId, CompiledNode[BaseModel, BaseModel]],
        registrations: dict[NodeId, NodeRegistration[BaseModel, BaseModel]],
    ) -> None:
        positions = {node_id: cls._position(compiled.node) for node_id, compiled in nodes.items()}
        for node_id, compiled in nodes.items():
            node = compiled.node
            if len(set(node.deps)) != len(node.deps):
                raise ValueError(f"node '{node_id}' has duplicate deps")
            for producer in node.deps:
                if producer not in nodes:
                    raise ValueError(f"node '{node_id}' has unknown dependency '{producer}'")
                if positions[producer] > positions[node_id]:
                    raise ValueError(f"node '{node_id}' depends on later phase/group producer '{producer}'")
            for requirement in registrations[node_id].contract.reads:
                producer = requirement.ref.producer
                if producer not in registrations:
                    raise ValueError(f"node '{node_id}' reads unknown producer '{producer}'")
                if producer not in node.deps:
                    raise ValueError(f"node '{node_id}' reads producer '{producer}' missing from deps")
                actual = registrations[producer].contract.output_type
                expected = requirement.ref.output_type
                if not issubclass(actual, expected):
                    raise TypeError(
                        f"node '{node_id}' reads producer '{producer}': incompatible Output "
                        f"{actual.__name__}; expected {expected.__name__}"
                    )
                if cls._phase(node) is ExecutionPhase.LLM and positions[producer] == positions[node_id]:
                    raise ValueError(f"node '{node_id}' reads producer '{producer}' in the same LLM group")
        # deps alone define ordering. reads never add another graph edge.
        cls._build_levels(nodes)

    @staticmethod
    def _build_levels(
        nodes: dict[NodeId, CompiledNode[BaseModel, BaseModel]],
    ) -> tuple[tuple[NodeId, ...], ...]:
        in_degree = {node_id: 0 for node_id in nodes}
        dependents: dict[NodeId, list[NodeId]] = {node_id: [] for node_id in nodes}
        for node_id, compiled in nodes.items():
            for producer in compiled.node.deps:
                if producer in nodes:
                    in_degree[node_id] += 1
                    dependents[producer].append(node_id)
        ready: list[NodeId] = [node_id for node_id, degree in in_degree.items() if degree == 0]
        levels: list[tuple[NodeId, ...]] = []
        visited = 0
        while ready:
            level = tuple(sorted(ready, key=lambda node_id: (-nodes[node_id].node.priority, node_id)))
            levels.append(level)
            visited += len(level)
            ready = []
            for producer in level:
                for consumer in dependents[producer]:
                    in_degree[consumer] -= 1
                    if in_degree[consumer] == 0:
                        ready.append(consumer)
        if visited != len(nodes):
            remaining = sorted(node_id for node_id, degree in in_degree.items() if degree)
            raise ValueError(f"cycle detected in DAG among nodes: {remaining}")
        return tuple(levels)
