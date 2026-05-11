import json

from app.application.llm.models import LLMResponse


class ResponseParser:

    def parse(self, raw: str) -> LLMResponse:

        text = raw
        data = {}

        try:

            json_start = raw.find("{")
            json_end = raw.rfind("}")

            if json_start != -1 and json_end != -1:

                json_str = raw[json_start:json_end + 1]

                data = json.loads(json_str)

                text = raw[:json_start].strip()

        except Exception:
            pass

        return LLMResponse(
            text=text,
            data=data,
            raw=raw
        )