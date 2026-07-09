from dataclasses import dataclass


@dataclass
class ConnectionEdgeCell:
    __table__ = "connection_edge_cells"
    __pk__    = "edge_uid"  # composite PK (edge_uid, x, y, z) in DB

    edge_uid: str
    x:        int
    y:        int
    z:        int
    seq:      int
