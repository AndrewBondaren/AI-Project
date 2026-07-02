"""Default barrier templates when world has no barrier_template_registry."""

from app.application.jsonValidation import barrier_template_defaults

DEFAULT_BARRIER_TEMPLATES: list[dict] = barrier_template_defaults()


def merge_barrier_registry(world) -> list[dict]:
    by_type: dict[str, dict] = {t["system_type"]: t for t in DEFAULT_BARRIER_TEMPLATES}
    for t in getattr(world, "barrier_template_registry", None) or []:
        if isinstance(t, dict) and t.get("system_type"):
            by_type[t["system_type"]] = t
    return list(by_type.values())


def lookup_barrier_template(world, system_type: str) -> dict | None:
    for t in merge_barrier_registry(world):
        if t.get("system_type") == system_type:
            return t
    return None
