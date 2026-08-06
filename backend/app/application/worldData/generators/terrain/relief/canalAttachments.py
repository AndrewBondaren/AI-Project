"""Canal resolve + draw/build — one mechanism, two kinds (R28/R36q).

dataModel: ``EarthenCanal`` | ``StructureCanal``.
Terrain: ``draw_canal`` shared; ``build_canal`` dispatches by type.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.dataModel.terrain.relief.canal import Canal, EarthenCanal, StructureCanal
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import (
    WorldCanalTemplateRegistry,
)

# R21 / canal why + fallback tokens (RELIEF-T-48)
WHY_UNKNOWN_STRUCTURE_CANAL = "unknown_structure_canal"
WHY_UNKNOWN_CANAL_REF = "unknown_canal_ref"
FALLBACK_NO_CANAL = "no_canal"
EVENT_CANAL_CUT_NO_CELLS = "canal_cut_no_cells"
EVENT_R21_FALLBACK = "r21_fallback"


@dataclass(frozen=True, slots=True)
class CanalDrawResult:
    """Flat projection for Grade SQL / Intent (one cut drawn)."""

    earthen_canal: bool
    structure_refs: tuple[str, ...]
    structure_canal: str | None = None


EMPTY_DRAW = CanalDrawResult(
    earthen_canal=False, structure_refs=(), structure_canal=None,
)


def normalize_structure_canal_ref(structure_canal: str | None) -> str | None:
    return (structure_canal or "").strip() or None


def draw_canal(canal: Canal) -> CanalDrawResult:
    """Shared stamp projection — kind-agnostic output shape."""
    if isinstance(canal, EarthenCanal):
        return CanalDrawResult(
            earthen_canal=True,
            structure_refs=(),
            structure_canal=canal.system_type,
        )
    return CanalDrawResult(
        earthen_canal=False,
        structure_refs=tuple(canal.structure_refs),
        structure_canal=canal.system_type,
    )


def _build_earthen(canal: EarthenCanal) -> CanalDrawResult:
    return draw_canal(canal)


def _build_structure(canal: StructureCanal) -> CanalDrawResult:
    return draw_canal(canal)


_BUILD_HANDLERS: dict[type, Callable[[Canal], CanalDrawResult]] = {
    EarthenCanal: _build_earthen,  # type: ignore[dict-item]
    StructureCanal: _build_structure,  # type: ignore[dict-item]
}


def build_canal(
    canal: Canal,
    *,
    extra_structure_refs: tuple[str, ...] = (),
) -> CanalDrawResult:
    """Kind handler + shared ``draw_canal``; optional BAR-1 fence refs with earthen."""
    handler = _BUILD_HANDLERS[type(canal)]
    drawn = handler(canal)
    if not extra_structure_refs:
        return drawn
    if not isinstance(canal, EarthenCanal):
        return drawn
    return CanalDrawResult(
        earthen_canal=drawn.earthen_canal,
        structure_refs=drawn.structure_refs + tuple(extra_structure_refs),
        structure_canal=drawn.structure_canal,
    )


def canal_from_registry_ref(
    canal_ref: str,
    registry: WorldCanalTemplateRegistry,
) -> Canal | None:
    """Lookup once. ``None`` = unknown ref (caller applies R21)."""
    entry = registry.entry_for(canal_ref)
    if entry is None:
        return None
    return entry.to_canal()


def resolve_knobs_canal(
    *,
    earthen_canal: bool | None,
    structure_canal: str | None,
    structure_refs: tuple[str, ...],
    registry: WorldCanalTemplateRegistry,
) -> Canal | None:
    """Normal-path canal from grade knobs (pure; no R21 warn).

    ``structure_canal`` → registry. Unknown → StructureCanal empty refs (audit).
    Earthen knobs may carry flat ``structure_refs`` (fence) via ``build_canal`` later.
    """
    ref = normalize_structure_canal_ref(structure_canal)
    if ref is not None:
        found = canal_from_registry_ref(ref, registry)
        if found is None:
            return StructureCanal(system_type=ref, structure_refs=[])
        return found
    if earthen_canal is True:
        return EarthenCanal()
    return None


def knobs_extra_structure_refs(
    *,
    earthen_canal: bool | None,
    structure_canal: str | None,
    structure_refs: tuple[str, ...],
) -> tuple[str, ...]:
    """Flat fence refs only when not using ``structure_canal`` (R28)."""
    del earthen_canal  # knobs earthen does not gate flat fence refs
    if normalize_structure_canal_ref(structure_canal) is not None:
        return ()
    return tuple(structure_refs)

def aggregate_canals(canals: Sequence[Canal]) -> Canal | None:
    """Segment aggregate: same kind; union structure refs; one system_type or drop."""
    if not canals:
        return None
    if all(isinstance(c, EarthenCanal) for c in canals):
        types = {c.system_type for c in canals if isinstance(c, EarthenCanal) and c.system_type}
        st = next(iter(types)) if len(types) == 1 else None
        return EarthenCanal(system_type=st)
    if all(isinstance(c, StructureCanal) for c in canals):
        typed = [c for c in canals if isinstance(c, StructureCanal)]
        ids = {c.system_type for c in typed}
        if len(ids) != 1:
            return None
        refs: list[str] = []
        seen: set[str] = set()
        for c in typed:
            for r in c.structure_refs:
                if r not in seen:
                    seen.add(r)
                    refs.append(r)
        return StructureCanal(system_type=typed[0].system_type, structure_refs=refs)
    # Mixed kinds — no single canal
    return None
