"""Shared connection defaults: sidewalk, lanes — district + city entry edges."""

_AUTO_SIDEWALK: dict[str, bool] = {
    "road":    True,
    "highway": True,
}

_DEFAULT_LANES: dict[str, int] = {
    "road":    1,
    "highway": 2,
}


def primary_connection(template: dict) -> dict:
    connections = template.get("connections") or []
    return connections[0] if connections else {}


def resolve_has_sidewalk(template: dict, connection_type: str | None = None) -> bool:
    """
    has_sidewalk для district/city edges.
    Приоритет: connections[0].sidewalk → auto по connection_type.
    """
    primary = primary_connection(template)
    ct = connection_type or primary.get("connection_type") or "road"
    sidewalk_decl = primary.get("sidewalk")
    if sidewalk_decl is not None:
        return bool(sidewalk_decl)
    return _AUTO_SIDEWALK.get(ct, False)


def resolve_lanes_per_side(template: dict, connection_type: str | None = None) -> int:
    primary = primary_connection(template)
    ct = connection_type or primary.get("connection_type") or "road"
    return int(primary.get("lanes_per_side") or _DEFAULT_LANES.get(ct, 1))
