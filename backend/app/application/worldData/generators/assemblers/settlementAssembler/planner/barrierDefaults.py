"""Default barrier templates when world has no barrier_template_registry."""

DEFAULT_BARRIER_TEMPLATES: list[dict] = [
    {
        "system_type":    "wooden_fence",
        "glossary_ref":   "barrier_wooden_fence",
        "wall_material":  {"pick_from": ["wood"]},
        "height_levels":  {"min": 1, "max": 1},
        "gates":          {"min": 1, "max": 2},
    },
    {
        "system_type":    "stone_fence",
        "glossary_ref":   "barrier_stone_fence",
        "wall_material":  {"pick_from": ["stone"]},
        "height_levels":  {"min": 1, "max": 2},
        "gates":          {"min": 1, "max": 4},
    },
    {
        "system_type":    "city_wall",
        "glossary_ref":   "barrier_city_wall",
        "wall_material":  {"pick_from": ["stone"]},
        "height_levels":  {"min": 2, "max": 5},
        "gates":          {"min": 1, "max": 6},
    },
]


def merge_barrier_registry(world) -> list[dict]:
    by_type: dict[str, dict] = {t["system_type"]: t for t in DEFAULT_BARRIER_TEMPLATES}
    for t in getattr(world, "barrier_template_registry", None) or []:
        key = t.get("system_type") or t.get("system_name")
        if key:
            by_type[key] = t
    return list(by_type.values())


def lookup_barrier_template(world, system_type: str) -> dict | None:
    for t in merge_barrier_registry(world):
        if t.get("system_type") == system_type:
            return t
    return None
