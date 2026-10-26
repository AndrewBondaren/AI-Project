"""Relief world-ref validation — barrier/canal registry checks (TZ relief).

Domain-level checks shared by the world-import seam: an outline's
``structure_refs`` / ``structure_canal`` must resolve in the target
world's ``barrier_template_registry`` / ``canal_template_registry``.
"""

from __future__ import annotations

from app.application.jsonValidation.worldRow import (
    barrier_templates,
    canal_templates,
)
from app.application.worldData.generators.terrain.relief.canal.outlineCollect import (
    collect_outline_structure_canal_refs,
    collect_outline_structure_refs,
)
from app.application.templateLibrary.reliefErrors import ReliefValidationError
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def validate_relief_world_refs(world, outline: ReliefTemplate) -> None:
    """Outline structure refs must resolve in the world barrier/canal registries."""
    barrier_keys = {e.system_type for e in barrier_templates(world).root}
    _check_structure_refs(outline, barrier_keys)
    _check_structure_canal(outline, world)


def _check_structure_refs(outline: ReliefTemplate, barrier_keys: set[str]) -> None:
    refs = collect_outline_structure_refs(outline)
    if not refs:
        return
    if not barrier_keys:
        raise ReliefValidationError(
            "structure_refs present but barrier_template_registry is empty: "
            f"{sorted(refs)}",
        )
    unknown = sorted(refs - barrier_keys)
    if unknown:
        raise ReliefValidationError(
            f"structure_refs unknown in barrier_template_registry: {unknown}",
        )


def _check_structure_canal(outline: ReliefTemplate, world: object) -> None:
    """``structure_canal`` ∈ ``canal_template_registry``; nested barrier refs."""
    canal_refs = collect_outline_structure_canal_refs(outline)
    if not canal_refs:
        return
    reg = canal_templates(world)
    known = {e.system_type for e in reg.root}
    unknown = sorted(canal_refs - known)
    if unknown:
        raise ReliefValidationError(
            f"structure_canal unknown in canal_template_registry: {unknown}",
        )
    barrier_keys = {e.system_type for e in barrier_templates(world).root}
    nested: set[str] = set()
    for ref in canal_refs:
        entry = reg.entry_for(ref)
        if entry is None or entry.structure is None:
            continue
        nested.update(entry.structure.structure_refs)
    if not nested:
        return
    if not barrier_keys:
        raise ReliefValidationError(
            "canal structure_refs present but barrier_template_registry "
            f"is empty: {sorted(nested)}",
        )
    bad = sorted(nested - barrier_keys)
    if bad:
        raise ReliefValidationError(
            "canal_template_registry.structure.structure_refs unknown "
            f"in barrier_template_registry: {bad}",
        )
