"""Single node status enum; ownership: engine dataModel (DAG-TYPING-1)."""

from enum import Enum


class NodeStatus(str, Enum):
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    GATED = "gated"
