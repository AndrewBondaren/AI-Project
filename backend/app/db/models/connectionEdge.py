from dataclasses import dataclass

from app.db.mapper import bool_col, json_nullable_col


@dataclass
class ConnectionEdge:
    __table__ = "connection_edges"
    __pk__    = "edge_uid"

    edge_uid:        str
    from_node_uid:   str
    to_node_uid:     str
    connection_type: str
    graph_level:     str   # "world"|"city"|"district"|"area"
    world_uid:       str

    bidirectional:        bool      = bool_col(default=True)
    lanes_per_side:       int       = 1
    width_cells:          int | None = None
    bridge_subtype:       str | None = None
    parent_edge_uid:      str | None = None
    side:                 str | None = None   # "left"|"right" — только для sidewalk
    material:             str | None = None
    condition:            int        = 100
    features:             list | None = json_nullable_col(default=None)
    lighting_type:        str | None = None
    danger_level:         str        = "none"
    has_sidewalk:         bool       = bool_col(default=False)
    under_construction:   bool       = bool_col(default=False)
    under_repair:         bool       = bool_col(default=False)
    street_objects:       list | None = json_nullable_col(default=None)
    traversal_conditions: dict | None = json_nullable_col(default=None)
