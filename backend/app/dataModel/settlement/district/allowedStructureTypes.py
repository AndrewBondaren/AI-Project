"""CITY-T-2a — ``allowed_structure_types`` null / [] / list.

Not wired into packing by this module; DistrictAssembler calls it with a catalog.
"""

from __future__ import annotations

from collections.abc import Iterable


def allowed_fill_structure_types(
    allowed: list[str] | None,
    catalog_structure_types: Iterable[str],
) -> tuple[str, ...]:
    """Fill types for packing (required is separate).

    ``None`` / omit → all catalog ``structure_type`` keys, sorted.
    ``[]`` → no fill (required only).
    list → those types (order preserved, unknown keys kept for the caller to skip).
    """
    if allowed is None:
        return tuple(sorted(set(catalog_structure_types)))
    seen: set[str] = set()
    out: list[str] = []
    for name in allowed:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return tuple(out)
