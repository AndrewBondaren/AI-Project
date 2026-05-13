class DSLFailureProjector:

    def project(self, failed_nodes, state):

        result = []

        for node_id, error in failed_nodes.items():

            result.append({
                "dsl_task": state.node_dsl.get(node_id),
                "error": error,
                "input": state.node_inputs.get(node_id),
                "output": state.node_results.get(node_id),
                "node_id": node_id,  # debug only
            })

        return result