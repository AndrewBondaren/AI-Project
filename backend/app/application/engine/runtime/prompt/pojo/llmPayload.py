"""One group's prepared POJO inputs and explicit client transport projection."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.application.engine.prompt.schemaBuilder import build_strict_schema
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection

_RESERVED_KEYS = frozenset(("player_message", "language", "dsl", "response_format"))


def _require_tuple(value: object) -> None:
    if not isinstance(value, tuple) or not value:
        raise ValueError("LLM payload requires a nonempty tuple of sections")


@dataclass(frozen=True, kw_only=True)
class LLMPayload:
    player_message: str
    language: str
    global_dsl: str
    sections: tuple[NodeSection[BaseModel], ...]

    def __post_init__(self) -> None:
        _require_tuple(self.sections)
        nodes = tuple(section.node_id for section in self.sections)
        if len(set(nodes)) != len(nodes):
            raise ValueError("duplicate LLM payload node ID")
        if set(nodes).intersection(_RESERVED_KEYS):
            raise ValueError("LLM node ID collides with reserved transport key")

    @property
    def response_format_schema(self) -> dict[str, object]:
        return build_strict_schema({
            section.node_id: section.output_type.model_json_schema() for section in self.sections
        })

    def to_user_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "player_message": self.player_message, "language": self.language,
            "response_format": self.response_format_schema,
        }
        payload.update((section.node_id, section.to_dict()) for section in self.sections)
        return payload

    def to_dict(self) -> dict[str, object]:
        return {**self.to_user_dict(), "dsl": self.global_dsl}
