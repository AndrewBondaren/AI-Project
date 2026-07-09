from dataclasses import dataclass

from app.db.mapper import json_nullable_col


@dataclass
class ConnectionNode:
    __table__ = "connection_nodes"
    __pk__    = "node_uid"

    node_uid:    str
    x:           int
    y:           int
    z:           int
    node_type:   str   # "intersection"|"settlement_gate"|"portal"|"building_entrance"|"location_hub"|"waypoint"
    graph_level: str   # "world"|"city"|"district"|"area"
    world_uid:   str

    location_uid: str | None = None

    # только для node_type="portal"
    portal_type:                      str | None = None
    portal_destinations:              list | None = json_nullable_col(default=None)
    portal_bidirectional:             int | None = None   # 0|1|null — nullable bool
    portal_is_active:                 int | None = None   # 0|1|null
    portal_blocked_behavior_override: str | None = None
