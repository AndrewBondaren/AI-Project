import json
from typing import Dict, Any, Optional


class LLMResponse:
    def __init__(self, text: str, data: Optional[Dict[str, Any]] = None):
        self.text = text
        self.data = data or {}


class ResponseParser:

    def parse(self, raw: str) -> LLMResponse:
        """
        Принимает сырой ответ LLM и нормализует его
        """

        text = raw
        data = {}

        # попытка вытащить JSON блок
        try:
            json_start = raw.find("{")
            json_end = raw.rfind("}")

            if json_start != -1 and json_end != -1:
                json_str = raw[json_start:json_end + 1]
                data = json.loads(json_str)

                # чистим текст от JSON
                text = raw[:json_start].strip()

        except Exception:
            # если JSON сломан — просто игнорируем
            pass

        return LLMResponse(text=text, data=data)