from dataclasses import asdict, dataclass

from app.application.engine.prompt.pojo.nodeSection import NodeSection


@dataclass
class LLMPayload:
    player_message: str
    language: str # fron front
    contract_json: dict
    sections: dict[str, NodeSection]  # node_id → NodeSection

    def to_dict(self) -> dict:
        payload = {
            "player_message": self.player_message,
            "language": self.language,
            "contract_json": self.contract_json,
        }
        for node_id, section in self.sections.items():
            payload[node_id] = asdict(section)
        return payload