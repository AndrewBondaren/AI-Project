class DSLAggregator:

#DSLAggregator тоже остаётся, но у него есть баг: читает state.node_dsl которого нет в ExecutionState. Это отдельный разговор — сейчас не трогаем?
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