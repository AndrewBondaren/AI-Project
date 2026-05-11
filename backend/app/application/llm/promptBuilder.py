import json


class PromptBuilder:

    def build(self, message: str, contract_model, session=None):

        system = """
[ROLE]
structured_ai_engine

[MODE]
json_only

[CONSTRAINTS]
- output must match schema exactly
- no additional fields allowed
- no markdown
- no explanation

[SCHEMA]
{...json schema here...}

[INPUT]
{...user payload...}

[OUTPUT RULE]
return only valid JSON object
"""

        schema = contract_model.model_json_schema()

        user_payload = {
            "message": message,
            "schema": schema,
        }

        if session:
            user_payload["state"] = getattr(session, "state", None)

        user = json.dumps(user_payload, ensure_ascii=False)

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]