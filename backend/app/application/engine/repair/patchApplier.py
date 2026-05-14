from typing import Any, Dict, List


class PatchApplier:
    """
    Applies validated repair patches to ExecutionState.

    Responsibility:
    - mutate state based on LLM repair output
    - NO validation
    - NO business logic
    - NO inference
    """

    def apply(self, state, repair_response: Dict[str, Any]) -> None:
        patches = self._extract_patches(repair_response)

        for patch in patches:
            self._apply_patch(state, patch)

        # optional: recompute execution order consistency
        state.execution_order.append("__repair_applied__")

    # -------------------------
    # extraction layer
    # -------------------------
    def _extract_patches(self, repair_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Normalizes different possible LLM outputs into patch list.
        """

        if not isinstance(repair_response, dict):
            return []

        # expected format
        if "patches" in repair_response:
            return repair_response["patches"]

        # fallback (if model returns direct mapping)
        if "failed_tasks" in repair_response:
            return self._convert_failed_tasks(repair_response["failed_tasks"])

        return []

    # -------------------------
    # normalization layer
    # -------------------------
    def _convert_failed_tasks(self, failed_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Converts legacy format into patch format.
        """
        patches = []

        for task in failed_tasks:
            if "node_id" in task and "output" in task:
                patches.append({
                    "node_id": task["node_id"],
                    "output": task["output"]
                })

        return patches

    # -------------------------
    # mutation layer
    # -------------------------
    def _apply_patch(self, state, patch: Dict[str, Any]) -> None:
        node_id = patch.get("node_id")
        output = patch.get("output")

        if not node_id:
            return

        # update results
        state.node_results[node_id] = output

        # mark as success
        state.node_status[node_id] = "success"

        # clear errors if exist
        if node_id in state.node_errors:
            del state.node_errors[node_id]

        # maintain execution order consistency
        if node_id not in state.execution_order:
            state.execution_order.append(node_id)