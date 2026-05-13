import json


class LLMStructuredExecutor:

    def __init__(self, max_retries: int = 5):
        self.max_retries = max_retries

    # -----------------------------
    # MAIN ENTRY
    # -----------------------------

    async def execute(
        self,
        *,
        client,
        model: str,
        messages: list,
        contract,
    ):
        """
        Returns validated contract object or raises error
        """

        repair_messages = list(messages)

        for attempt in range(self.max_retries):

            raw = await client.chat(
                model=model,
                messages=repair_messages,
            )

            # -------------------------
            # STEP 1: JSON PARSE
            # -------------------------
            try:
                parsed = json.loads(raw)

            except Exception as e:
                repair_messages.append(self._repair_msg(
                    stage="json_parse",
                    error=str(e),
                    raw=raw,
                    contract=contract
                ))
                continue

            # -------------------------
            # STEP 2: SCHEMA VALIDATION
            # -------------------------
            try:
                validated = contract.model_validate(parsed)
                return validated

            except Exception as e:
                repair_messages.append(self._repair_msg(
                    stage="schema_validation",
                    error=str(e),
                    raw=raw,
                    contract=contract
                ))
                continue

        raise RuntimeError("LLMStructuredExecutor failed after max retries")

    # -----------------------------
    # REPAIR MESSAGE BUILDER
    # -----------------------------

    def _repair_msg(self, stage: str, error: str, raw: str, contract):

        return {
            "role": "system",
            "content": json.dumps({
                "type": "repair",
                "stage": stage,
                "error": error,
                "expected_schema": getattr(contract, "model_json_schema", lambda: None)(),
                "bad_output": raw,
                "hint": "Return ONLY valid JSON matching schema"
            })
        }