from dataclasses import dataclass

@dataclass
class PromptContext:
    message: str
    node_results: dict
    session: any = None
    errors: list = None
    task_type: str = None