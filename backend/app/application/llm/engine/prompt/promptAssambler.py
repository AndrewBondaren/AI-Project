import json

class PromptAssembler:

    def build_system(self, dsl: str, context):
        return dsl

    def build_user(self, context):

        payload = {
            "message": context.message,
            "results": context.node_results,
        }

        if context.errors is not None:
            payload["errors"] = context.errors

        return json.dumps(payload, ensure_ascii=False)