class RepairPatchApplier:
    """
    Applies queued LLM node outputs to DAG execution state after all passes.

    Includes successful outputs with or without repair. Does not repair outputs,
    write world data, or invoke World Snapshot. Not a world transaction:
    the executor already exposes outputs before this final bookkeeping step.
    """

    def apply(self, state) -> None:

        patches = state.pending_patches

        if not patches:
            return

        # Проверяем структуру записей до обновления состояния исполнения.
        for patch in patches:
            if not patch.get("node_id") or "output" not in patch:
                raise ValueError(
                    f"Invalid patch — missing node_id or output: {patch}"
                )

        # Обновляем результаты DAG; rollback и world commit здесь отсутствуют.
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