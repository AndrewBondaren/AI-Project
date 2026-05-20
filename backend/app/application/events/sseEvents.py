from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel


class SSEEventType(str, Enum):
    NODE_STATUS = "node_status"
    THINKING    = "thinking"
    RESULT      = "result"
    ERROR       = "error"
    CANCELLED   = "cancelled"
    CHUNK       = "chunk"       # reserved, phase 2


class NodePhase(str, Enum):
    EXECUTING = "executing"
    REPAIRING = "repairing"
    DONE      = "done"
    FAILED    = "failed"


class NodeStatusEvent(BaseModel):
    type:      Literal[SSEEventType.NODE_STATUS] = SSEEventType.NODE_STATUS
    node_id:   str
    task_type: str
    phase:     NodePhase


class ThinkingEvent(BaseModel):
    type:       Literal[SSEEventType.THINKING] = SSEEventType.THINKING
    node_id:    str
    text:       str
    elapsed_ms: int


class ResultEvent(BaseModel):
    type:     Literal[SSEEventType.RESULT] = SSEEventType.RESULT
    response: Any


class ErrorEvent(BaseModel):
    type:    Literal[SSEEventType.ERROR] = SSEEventType.ERROR
    message: str


class CancelledEvent(BaseModel):
    type:       Literal[SSEEventType.CANCELLED] = SSEEventType.CANCELLED
    session_id: str
    request_id: str


# reserved — not emitted yet
class ChunkEvent(BaseModel):
    type:    Literal[SSEEventType.CHUNK] = SSEEventType.CHUNK
    node_id: str
    text:    str


SSEEvent = NodeStatusEvent | ThinkingEvent | ResultEvent | ErrorEvent | CancelledEvent | ChunkEvent
