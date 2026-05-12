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

        if context.session is not None:
            payload["session"] = context.session

        return json.dumps(payload, ensure_ascii=False)