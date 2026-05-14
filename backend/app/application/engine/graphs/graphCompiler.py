from collections import defaultdict, deque
from app.application.engine.graphs.executionPlan import ExecutionPlan
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY


class GraphCompiler:

    def __init__(self, rule_engine, rule_compiler):
        self.rule_engine = rule_engine
        self.rule_compiler = rule_compiler

    def compile(self, state) -> ExecutionPlan:

        # берём все ноды из registry
        all_registrations = NODE_REGISTRY.all()

        # компилируем правила и фильтруем
        compiled_nodes = self._compile_nodes(all_registrations)
        filtered = self._filter(compiled_nodes, state)

        # строим DAG и уровни
        dag = self._build_dag(filtered)
        levels = self._topological_levels(dag, filtered)
        optimized = self._optimize(levels, filtered)

        return ExecutionPlan(
            levels=optimized,
            nodes={n.node.id: n for n in filtered},
            priority_sorted=[n.node.id for n in sorted(filtered, key=lambda n: -n.node.priority)],
            estimated_cost=self._estimate_cost(filtered)
        )

    # --------------------------------------------------

    def _compile_nodes(self, registrations) -> list:
        """Компилируем rules каждой ноды → CompiledNode"""
        from app.application.engine.nodes.pojo.compiledNode import CompiledNode

        compiled = []
        for node_id, registration in registrations.items():
            node = registration.node_cls
            compiled_rules = self.rule_compiler.compile(node.rules)
            compiled.append(CompiledNode(node=node, compiled_rules=compiled_rules))

        return compiled

    def _filter(self, compiled_nodes, state) -> list:
        """Оставляем только ноды которые подходят под текущий state"""
        return [
            cn for cn in compiled_nodes
            if self.rule_engine.evaluate(cn, state)
        ]

    def _build_dag(self, compiled_nodes) -> dict[str, list[str]]:
        """
        Строим граф зависимостей.
        dag[node_id] = [node_id, ...] — список нод от которых зависит нода.
        """
        node_ids = {cn.node.id for cn in compiled_nodes}
        dag = defaultdict(list)

        for cn in compiled_nodes:
            for dep in cn.node.deps:
                if dep not in node_ids:
                    raise ValueError(
                        f"Node '{cn.node.id}' depends on '{dep}' "
                        f"but '{dep}' is not in filtered nodes"
                    )
                dag[cn.node.id].append(dep)

        return dag

    def _topological_levels(self, dag, compiled_nodes) -> list[list[str]]:
        """
        Kahn's algorithm — разбивает ноды на уровни.
        Ноды одного уровня можно исполнять параллельно.

        level 0 — ноды без зависимостей
        level 1 — ноды зависящие только от level 0
        level N — ноды зависящие от level N-1
        """
        # считаем in-degree (кол-во зависимостей) для каждой ноды
        in_degree = {cn.node.id: 0 for cn in compiled_nodes}

        # reverse dag: кто зависит от данной ноды
        dependents = defaultdict(list)

        for node_id, deps in dag.items():
            in_degree[node_id] = len(deps)
            for dep in deps:
                dependents[dep].append(node_id)

        # стартуем с нод у которых нет зависимостей
        queue = deque([
            node_id for node_id, degree in in_degree.items()
            if degree == 0
        ])

        levels = []

        while queue:
            # все ноды в queue — это текущий уровень
            current_level = list(queue)
            levels.append(current_level)
            queue.clear()

            next_level_candidates = set()

            for node_id in current_level:
                for dependent in dependents[node_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level_candidates.add(dependent)

            queue.extend(next_level_candidates)

        # проверка на циклы
        visited = sum(len(level) for level in levels)
        if visited != len(in_degree):
            raise ValueError("Cycle detected in DAG")

        return levels

    def _optimize(self, levels, compiled_nodes) -> list[list[str]]:
        """Сортируем ноды внутри уровня по приоритету"""
        node_map = {cn.node.id: cn for cn in compiled_nodes}

        return [
            sorted(
                level,
                key=lambda node_id: -node_map[node_id].node.priority
            )
            for level in levels
        ]

    def _estimate_cost(self, compiled_nodes) -> float:
        """Суммируем стоимость всех нод"""
        return sum(cn.node.cost.cpu for cn in compiled_nodes)