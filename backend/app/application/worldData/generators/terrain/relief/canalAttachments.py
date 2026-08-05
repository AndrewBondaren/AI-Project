"""Resolve canal knobs / registry entry → attachments — R28/R36q / RELIEF-T-47."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.dataModel.terrain.relief.canalTemplateEntry import CanalTemplateEntry
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
class CanalAttachments:
    """Resolved canal for Intent + Grade (one cut)."""

    earthen_canal: bool
    structure_refs: tuple[str, ...]
    structure_canal: str | None = None

    def grade_fields(self) -> dict[str, bool | tuple[str, ...] | str | None]:
        """Single projection for Grade factory / persist (RELIEF-T-58)."""
        return {
            "earthen_canal": self.earthen_canal,
            "structure_refs": self.structure_refs,
            "structure_canal": self.structure_canal,
        }

    def intent_fields(self) -> dict[str, bool | tuple[str, ...]]:
        """Projection for RoadShoulderIntent (refs + earthen; no canal_ref yet)."""
        return {
            "earthen_canal": self.earthen_canal,
            "structure_refs": self.structure_refs,
        }


EMPTY_CANAL = CanalAttachments(earthen_canal=False, structure_refs=())
# R36p: enable cut, omit canal_ref → earthen-only (RELIEF-T-55)
EMPTY_EARTHEN_CUT = CanalAttachments(earthen_canal=True, structure_refs=())


def normalize_structure_canal_ref(structure_canal: str | None) -> str | None:
    return (structure_canal or "").strip() or None


def attachments_from_canal_entry(
    entry: CanalTemplateEntry,
) -> tuple[bool, tuple[str, ...]]:
    refs: tuple[str, ...] = ()
    if entry.structure is not None:
        refs = tuple(entry.structure.structure_refs)
    earthen = bool(entry.earthen_canal) if entry.earthen_canal is not None else False
    return earthen, refs


def attachments_from_registry_ref(
    canal_ref: str,
    registry: WorldCanalTemplateRegistry,
) -> CanalAttachments | None:
    """Lookup once. ``None`` = unknown ref (caller applies R21)."""
    entry = registry.entry_for(canal_ref)
    if entry is None:
        return None
    earthen, refs = attachments_from_canal_entry(entry)
    return CanalAttachments(
        earthen_canal=earthen,
        structure_refs=refs,
        structure_canal=canal_ref,
    )


def no_canal_for_ref(canal_ref: str) -> CanalAttachments:
    """Empty attachments keeping the unknown ref for audit."""
    return CanalAttachments(
        earthen_canal=False,
        structure_refs=(),
        structure_canal=canal_ref,
    )


def resolve_knobs_canal(
    *,
    earthen_canal: bool | None,
    structure_canal: str | None,
    structure_refs: tuple[str, ...],
    registry: WorldCanalTemplateRegistry,
) -> CanalAttachments:
    """Normal-path canal from grade knobs (pure; no R21 warn).

    ``structure_canal`` wins materials from registry. Unknown → empty + ref.
    """
    ref = normalize_structure_canal_ref(structure_canal)
    if ref is None:
        return CanalAttachments(
            earthen_canal=bool(earthen_canal),
            structure_refs=tuple(structure_refs),
            structure_canal=None,
        )
    att = attachments_from_registry_ref(ref, registry)
    if att is None:
        return no_canal_for_ref(ref)
    return att


def aggregate_canal_attachments(
    atts: Sequence[CanalAttachments],
) -> CanalAttachments:
    """Segment Intent aggregate over per-seed cuts (OR earthen, union refs)."""
    if not atts:
        return EMPTY_CANAL
    earthen = any(a.earthen_canal for a in atts)
    refs: list[str] = []
    seen: set[str] = set()
    for a in atts:
        for r in a.structure_refs:
            if r not in seen:
                seen.add(r)
                refs.append(r)
    canal_ids = [a.structure_canal for a in atts if a.structure_canal]
    unique = set(canal_ids)
    structure_canal = canal_ids[0] if len(unique) == 1 else None
    return CanalAttachments(
        earthen_canal=earthen,
        structure_refs=tuple(refs),
        structure_canal=structure_canal,
    )
