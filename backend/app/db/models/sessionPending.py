from dataclasses import dataclass


@dataclass
class SessionPending:
    __table__ = "session_pending"
    __pk__    = "session_id"

    session_id:   str
    player_input: str
    snapshot:     str | None = None
    created_at:   str | None = None
