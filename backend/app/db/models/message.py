from dataclasses import dataclass, field


@dataclass
class Turn:
    __table__ = "turns"
    __pk__    = "turn_id"

    turn_id:      str
    session_id:   str
    player_input: str
    created_at:   str
    game_tick:    int | None = None


@dataclass
class Message:
    __table__ = "messages"
    __pk__    = "message_id"

    message_id:   str
    turn_id:      str
    session_id:   str
    created_at:   str
    message_type: str        = field(default='narrative')
    llm_output:   str | None = None
    game_tick:    int | None = None


@dataclass
class NodeExecutionLog:
    __table__ = "node_execution_logs"
    __pk__    = "log_id"

    log_id:      str
    turn_id:     str
    session_id:  str
    node_type:   str
    created_at:  str
    node_input:  str | None = None
    node_output: str | None = None
    duration_ms: int | None = None
