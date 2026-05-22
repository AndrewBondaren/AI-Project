from dataclasses import asdict, dataclass

from app.application.engine.prompt.pojo.nodeSection import NodeSection


@dataclass
class LLMPayload:
    player_message: str
    language: str
    global_dsl: str
    response_format_schema: dict
    sections: dict[str, NodeSection]  # node_id -> NodeSection

    def to_dict(self) -> dict:
        payload = {
            "player_message": self.player_message,
            "language": self.language,
            "dsl": self.global_dsl,
            "response_format": self.response_format_schema,
        }
        for node_id, section in self.sections.items():
            payload[node_id] = asdict(section)
        return payload

    def to_user_dict(self) -> dict:
        """Payload without global_dsl — used when dsl is sent as system message."""
        payload = {
            "player_message": self.player_message,
            "language": self.language,
            "response_format": self.response_format_schema,
        }
        for node_id, section in self.sections.items():
            payload[node_id] = asdict(section)
        return payload
