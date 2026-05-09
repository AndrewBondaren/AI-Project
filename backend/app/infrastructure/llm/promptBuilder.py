import json


class PromptBuilder:
    def build(self, state: dict):

        system = """
You are a game engine AI.

You must:
- respond in structured JSON
- respect Power System rules
- never invent stats
"""

        user = f"""
STATE:
{json.dumps(state, indent=2)}

TASK:
Process user message and return game response.
"""

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]