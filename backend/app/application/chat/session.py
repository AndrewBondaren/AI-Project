from dataclasses import dataclass

@dataclass
class Session:
    llm_provider: str
    model: str
    user_id: str
    meta: dict
    max_tokens: int
    repair_iterations: int
    timeout: 60