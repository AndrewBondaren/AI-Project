from dataclasses import dataclass


@dataclass
class Message:
    __table__ = "messages"
    __pk__    = "message_id"

    message_id:   str
    session_id:   str
    created_at:   str
    player_input: str | None = None
    llm_output:   str | None = None
    game_tick:    int | None = None
