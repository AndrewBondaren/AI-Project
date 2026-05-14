from enum import Enum


class NodeStatus(str, Enum):
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"