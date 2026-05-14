from app.application.engine.graphs.executionPlan import ExecutionPlan


class GraphCompiler:

    def compile(self, nodes, state):

        filtered = self.filter(nodes, state)

        dag = self.build_dag(filtered)

        levels = self.topological_levels(dag)

        optimized = self.optimize(levels, nodes)

        return ExecutionPlan(
            levels=optimized,
            priority_sorted=self.sort_by_priority(filtered),
            estimated_cost=self.estimate_cost(filtered)
        )
    

#sorted(level, key=lambda n: (
#    -n.priority,
#    n.cost.cpu,
#    n.cost.llm_calls
#))