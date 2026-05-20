from collections import defaultdict, deque
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY
from app.application.engine.nodes.pojo.compiledNode import CompiledNode
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.dag.executionPlan import ExecutionPlan, LLMGroup


class GraphCompiler:

    def __init__(self, rule_engine, rule_compiler):
        self.rule_engine = rule_engine
        self.rule_compiler = rule_compiler
        self._compiled_nodes: list[CompiledNode] | None = None

    def precompile(self) -> None:
        """Однократная компиляция всех зарегистрированных нод при старте.
        Должна быть вызвана до первого compile()."""
        self._compiled_nodes = self._compile_nodes(NODE_REGISTRY.all())

    def compile(self, state) -> ExecutionPlan:
        if self._compiled_nodes is None:
            raise RuntimeError("GraphCompiler.precompile() must be called before compile()")

        filtered = self._filter(self._compiled_nodes, state)

        pre_llm, llm_nodes, post_llm = self._split_by_phase(filtered)

        pre_llm_levels  = self._build_levels(pre_llm)
        post_llm_levels = self._build_levels(post_llm)
        llm_groups      = self._build_llm_groups(llm_nodes)

        return ExecutionPlan(
            pre_llm_levels=pre_llm_levels,
            llm_groups=llm_groups,
            post_llm_levels=post_llm_levels,
            nodes={cn.node.id: cn for cn in filtered},
            estimated_cost=self._estimate_cost(filtered),
        )

    # --------------------------------------------------

    def _compile_nodes(self, registrations) -> list[CompiledNode]:
        compiled = []
        for node_id, registration in registrations.items():
            node = registration.node_cls()  # инстанциируем здесь
            compiled_rules = self.rule_compiler.compile(node.rules)
            compiled.append(CompiledNode(node=node, compiled_rules=compiled_rules))
        return compiled

    def _filter(self, compiled_nodes: list[CompiledNode], state) -> list[CompiledNode]:
        """Оставляем только ноды которые подходят под текущий state"""
        return [
            cn for cn in compiled_nodes
            if self.rule_engine.evaluate(cn, state)
        ]
    
    def _split_by_phase(
        self,
        compiled_nodes: list[CompiledNode],
    ) -> tuple[list[CompiledNode], list[CompiledNode], list[CompiledNode]]:
        """
        Делит ноды на три группы:
          - pre_llm  — PythonNode с phase="pre_llm"
          - llm      — LLMNode (phase не используется)
          - post_llm — PythonNode с phase="post_llm"
        """
        pre_llm  = []
        llm      = []
        post_llm = []

        for cn in compiled_nodes:
            node = cn.node
            if isinstance(node, LLMNode):
                llm.append(cn)
            elif isinstance(node, PythonNode):
                if node.phase == "pre_llm":
                    pre_llm.append(cn)
                else:
                    post_llm.append(cn)
            else:
                raise TypeError(
                    f"Node '{node.id}' is neither LLMNode nor PythonNode — "
                    f"не знаю в какую фазу поставить"
                )

        return pre_llm, llm, post_llm
    
    def _build_llm_groups(self, llm_nodes: list[CompiledNode]) -> list[LLMGroup]:
        """
        Группирует LLM-ноды по temperature, строит уровни внутри каждой группы,
        возвращает группы отсортированные по temperature ASC
        (низкая temperature → первой: анализ до генерации).
        """
        # собираем ноды по температуре
        buckets: dict[float, list[CompiledNode]] = defaultdict(list)
        for cn in llm_nodes:
            buckets[cn.node.temperature].append(cn)

        groups = []
        for temperature in sorted(buckets.keys()):
            group_nodes = buckets[temperature]
            levels = self._build_levels(group_nodes)
            groups.append(LLMGroup(temperature=temperature, levels=levels))

        return groups

    def _build_levels(self, compiled_nodes: list[CompiledNode]) -> list[list[str]]:
        """
        Kahn's algorithm — разбивает ноды на уровни.
        Ноды одного уровня можно исполнять параллельно.

        level 0 — ноды без зависимостей
        level 1 — ноды зависящие только от level 0
        level N — ноды зависящие от level N-1
        """
        if not compiled_nodes:
            return []
    
        node_ids = {cn.node.id for cn in compiled_nodes}
        node_map = {cn.node.id: cn for cn in compiled_nodes}

        # считаем in-degree (кол-во зависимостей) для каждой ноды
        in_degree:  dict[str, int]       = {cn.node.id: 0 for cn in compiled_nodes}

        # reverse dag: кто зависит от данной ноды
        dependents: dict[str, list[str]] = defaultdict(list)

        for cn in compiled_nodes:
            # учитываем только deps внутри текущего набора (фазы / группы)
            local_deps = [d for d in cn.node.deps if d in node_ids]
            in_degree[cn.node.id] = len(local_deps)
            for dep in local_deps:
                dependents[dep].append(cn.node.id)

        # стартуем с нод у которых нет зависимостей
        queue = deque(
            node_id for node_id, degree in in_degree.items() if degree == 0
        )

        levels = []

        while queue:
            # все ноды в queue — это текущий уровень
            current_level = list(queue)
            queue.clear()

            # сортируем по приоритету DESC внутри уровня
            current_level.sort(key=lambda nid: -node_map[nid].node.priority)
            levels.append(current_level)

            next_candidates: set[str] = set()
            for node_id in current_level:
                for dependent in dependents[node_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_candidates.add(dependent)

            queue.extend(next_candidates)

        visited = sum(len(level) for level in levels)
        if visited != len(in_degree):
            raise ValueError(
                f"Cycle detected in DAG among nodes: "
                f"{set(in_degree) - {n for lvl in levels for n in lvl}}"
            )

        return levels

    def _estimate_cost(self, compiled_nodes: list[CompiledNode]) -> float:
        """Суммируем стоимость всех нод"""
        return sum(cn.node.cost.cpu for cn in compiled_nodes)