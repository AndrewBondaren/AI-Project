import json


class RepairBuilder:

    def build(self, state, failed_nodes, dsl_keys):

        projected_failures = self._project_to_dsl(failed_nodes, state)

        return json.dumps({
            "message": state.message,
            "dsl_context": dsl_keys,
            "failed_tasks": projected_failures,
            "instruction": {
                "goal": "Fix only failed DSL tasks",
                "rules": [
                    "Do not modify successful outputs",
                    "Return only corrected DSL task outputs",
                    "Output must be valid JSON"
                ]
            }
        }, ensure_ascii=False)