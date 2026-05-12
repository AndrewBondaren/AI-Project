import asyncio

from typing import Dict, List
from datetime import datetime, timezone
from app.application.llm.engine.execution.executionTrace import ExecutionTrace


class DAGExecutor:

    async def execute(self, graph, state, context):

        self.context = context

        levels = self.build_levels(graph.nodes)

        for level in levels:
            await self.execute_level(graph, state, level)

        state.final_result = state.node_results
        return state

    # -------------------------
    # LEVEL BUILDER (deterministic)
    # -------------------------

    def build_levels(self, nodes: Dict[str, "Node"]) -> List[List[str]]:

        from collections import defaultdict, deque

        indegree = {n: 0 for n in nodes}
        graph = defaultdict(list)

        for node_id, node in nodes.items():
            for dep in node.deps:
                graph[dep].append(node_id)
                indegree[node_id] += 1

        queue = deque(sorted([n for n, d in indegree.items() if d == 0]))

        levels = []
        visited = set()

        while queue:
            level = []

            for _ in range(len(queue)):
                node = queue.popleft()
                visited.add(node)
                level.append(node)

            level.sort()
            levels.append(level)

            for node in level:
                for nxt in graph[node]:
                    indegree[nxt] -= 1
                    if indegree[nxt] == 0:
                        queue.append(nxt)

        if len(visited) != len(nodes):
            raise RuntimeError(f"Cyclic DAG detected. Visited={len(visited)} nodes")

        return levels

    # -------------------------
    # LEVEL EXECUTION
    # -------------------------

    async def execute_level(self, graph, state, level_nodes):

        tasks = [
            self.execute_node(graph.nodes[n], state)
            for n in sorted(level_nodes)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for node_id, result in zip(sorted(level_nodes), results):

            if isinstance(result, Exception):
                state.node_status[node_id] = "failed"
                state.node_errors.setdefault(node_id, []).append(
                    {"error": str(result)}
            )
            continue

        state.execution_order.append(node_id)

    # -------------------------
    # NODE EXECUTION
    # -------------------------

    async def execute_node(self, node, state):

        trace = ExecutionTrace(
            node_id=node.id,
            start_time=datetime.now(timezone.utc),
            input=dict(state.node_results)
        )

        state.node_status[node.id] = "running"

        try:
            executor = self.registry.get(node.type)
            result = await executor.execute(node, state, self.context)

            trace.output = result
            trace.status = "success"

            state.node_status[node.id] = "success"
            state.node_results[node.id] = result

            return result

        except Exception as e:

            state.node_status[node.id] = "failed"
            state.node_errors.setdefault(node.id, []).append(
                {"error": str(e)}
            )

            trace.status = "failed"
            trace.output = None

            raise

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)