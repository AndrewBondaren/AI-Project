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
    a_space: str
    a_level_uid: str | None
    a_host_location_uid: str | None
    a_node_uid: str | None
    a_x: int | None
    a_y: int | None
    a_z: int | None
    b_space: str
    b_level_uid: str | None
    b_host_location_uid: str | None
    b_node_uid: str | None
    b_x: int | None
    b_y: int | None
    b_z: int | None
