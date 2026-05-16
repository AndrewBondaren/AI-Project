from dataclasses import dataclass

@dataclass
class Session:
    llm_provider: str
    model: str
    user_id: str
    meta: dict
    max_tokens: int = 50000
    repair_iterations: int = 3
    language: str = "RU"
    max_passes: int = 3 #Todo send from front
    timeout: int = 60