"""SQL projection of Transition; behavior and defaults belong to the POJO."""

from dataclasses import dataclass, field


@dataclass
class TransitionRow:
    __table__ = "transitions"
    __pk__ = "transition_uid"

    transition_uid: str
    world_uid: str
    system_transition_type: str
    origin: str
    is_bidirectional: bool = field(metadata={"db_type": "bool"})
    is_active: bool = field(metadata={"db_type": "bool"})
    access_mechanic: list[str] = field(metadata={"db_type": "json_list"})
    type_params: dict = field(metadata={"db_type": "json_nullable"})
    display_name: str | None
    glossary_ref: str | None
    tag_refs: list[str] = field(metadata={"db_type": "json_list"})
    source_space: str
    source_level_uid: str | None
    source_host_location_uid: str | None
    source_node_uid: str | None
    source_x: int | None
    source_y: int | None
    source_z: int | None
    destination_space: str
    destination_level_uid: str | None
    destination_host_location_uid: str | None
    destination_node_uid: str | None
    destination_x: int | None
    destination_y: int | None
    destination_z: int | None
