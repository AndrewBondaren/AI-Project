from dataclasses import dataclass


@dataclass
class SessionSnapshot:
    session_id: str
    node_results: dict
    node_status: dict
    task_type: str
    original_message: str
