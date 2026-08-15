"""Collect canal / structure refs from ReliefTemplate outline — RELIEF-T-47."""

from __future__ import annotations

from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def collect_outline_structure_refs(outline: ReliefTemplate) -> set[str]:
    refs: set[str] = set(outline.structure_refs)
    for cond in outline.conditions:
        for case in cond.cases:
            refs.update(case.structure_refs)
            if case.bands:
                for band in case.bands:
                    refs.update(band.structure_refs)
    return refs


def collect_outline_structure_canal_refs(outline: ReliefTemplate) -> set[str]:
    canal_refs: set[str] = set()
    root_canal = getattr(outline, "structure_canal", None)
    if root_canal:
        canal_refs.add(str(root_canal))
    for cond in outline.conditions:
        for case in cond.cases:
            if case.structure_canal:
                canal_refs.add(str(case.structure_canal))
            if case.bands:
                for band in case.bands:
                    if band.structure_canal:
                        canal_refs.add(str(band.structure_canal))
    return canal_refs
