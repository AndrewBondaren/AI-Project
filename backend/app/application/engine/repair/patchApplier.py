class PatchApplier:
    """
    Транзакционно применяет накопленные патчи из state.pending_patches.
    Вызывается один раз в LLMExecutionEngine после всех passes.
    Либо все патчи применяются, либо ничего.
    """

    def apply(self, state) -> None:

        patches = state.pending_patches

        if not patches:
            return

        # валидируем все патчи перед мутацией — транзакция
        for patch in patches:
            if not patch.get("node_id") or "output" not in patch:
                raise ValueError(
                    f"Invalid patch — missing node_id or output: {patch}"
                )

        # все патчи валидны — применяем атомарно
        for patch in patches:
            self._apply_patch(state, patch)

        state.pending_patches.clear()

    def _apply_patch(self, state, patch: dict) -> None:

        node_id = patch["node_id"]
        output = patch["output"]

        state.node_results[node_id] = output
        state.node_status[node_id] = "success"

        if node_id in state.node_errors:
            del state.node_errors[node_id]

        if node_id not in state.execution_order:
            state.execution_order.append(node_id)