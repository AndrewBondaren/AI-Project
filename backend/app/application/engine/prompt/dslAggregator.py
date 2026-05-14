class DSLAggregator:

    def aggregate_dsl_keys(self, state):
        seen = set()
        result = []

        for node_id in state.execution_order:
            dsl = state.node_dsl.get(node_id)

            if not dsl:
                continue

            if dsl in seen:
                continue

            seen.add(dsl)
            result.append(dsl)

        return result