from app.application.engine.repair.pojo.nodeFailureContext import NodeFailureContext


class DSLFailureProjector:

    def project(self, failed_nodes: list, state) -> list[NodeFailureContext]:
        result = []
        for node in failed_nodes:
            result.append(NodeFailureContext(
                node_id=node.id,
                dsl_task=node.dsl,
                error_codes=self._get_error_codes(node.id, state),
                output=state.node_results.get(node.id),
            ))
        return result

    def _get_error_codes(self, node_id: str, state) -> list[str]:
        errors = state.node_errors.get(node_id)
        if not errors:
            return []
        return errors[-1].get("errors", [])