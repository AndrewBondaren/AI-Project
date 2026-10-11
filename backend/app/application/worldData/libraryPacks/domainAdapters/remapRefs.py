"""World-side / body ref remap helpers — TZ §2.

Shared raw-wire scanners of the heterogeneous registry columns: pointer
rows vs embedded plot layouts are told apart by ``_POINTER_UID_FIELD``;
entries that carry a declared ref field are remapped through their POJO
(``model_copy``) and the dump overlays the raw row so unknown keys
survive. Refs absent from ``uid_map`` — other packs, external bodies —
stay untouched.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    RELIEF_POLICY_REF_FIELDS, STRUCTURE_REF_FIELDS, structure_ref_model,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ReliefContextPickPolicy,
)
from app.db.models.world import World


def remap_pins(world: World, uid_map: Mapping[str, str]) -> bool:
    from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
    out = []
    changed = False
    for raw in world.library_pins or []:
        pin = LibraryPinEntry.model_validate(raw)
        uid = uid_map.get(pin.template_uid, pin.template_uid)
        changed = changed or uid != pin.template_uid
        out.append({**raw, 'template_uid': uid})
    if changed:
        world.library_pins = out
    return changed


def _remap_structure_refs(row: dict, uid_map: Mapping[str, str]) -> dict | None:
    """``structure`` uid refs of a plot-layout wire shape → instance uids.

    Declared ref fields of the structure domain (TZ §2) —
    ``PlotLayoutTemplate.main_building.structure`` and
    ``secondary_buildings[].structure`` — are rewritten through the
    POJO (``model_copy``); the dump overlays the raw row so unknown
    keys survive. Pointer rows (``_POINTER_UID_FIELD``) and dicts
    without ref parents are not layouts; a dict that carries a ref
    parent but fails the schema is a hard error, not a silent skip.
    Returns ``None`` when nothing matched — refs to other packs stay
    untouched.
    """
    try:
        plot = structure_ref_model(row, label="plot-layout")
    except ValueError as exc:
        raise LibraryPackValidationError(
            f"plot-layout row fails schema during ref remap: {exc}"
        ) from exc
    if plot is None:
        return None
    update: dict[str, Any] = {
        field.parent_field: value for field in STRUCTURE_REF_FIELDS
        if (value := field.remap(plot, uid_map)) is not None
    }
    if not update:
        return None
    return {**row, **plot.model_copy(update=update).model_dump(mode="json")}


def _remap_relief_pick_policy(world: World, uid_map: Mapping[str, str]) -> dict | None:
    """``relief_pick_policy.<context>.default_template_uid`` — the declared
    world-side ref field of the relief domain (TZ §2). Entries are
    remapped through ``ReliefContextPickPolicy``; the dump overlays the
    raw entry so unknown keys and non-policy fields stay untouched."""
    raw = world.relief_pick_policy or {}
    if not isinstance(raw, dict):
        return None
    out = dict(raw)
    changed = False
    for field in RELIEF_POLICY_REF_FIELDS:
        name = field.parent_field
        entry = out.get(name)
        if not isinstance(entry, dict):
            continue
        try:
            policy = ReliefContextPickPolicy.model_validate(entry)
        except ValueError as exc:
            raise LibraryPackValidationError(
                f"relief_pick_policy.{name} fails schema during ref remap: {exc}"
            ) from exc
        replacement = field.remap_entry(policy, uid_map)
        if replacement is not policy:
            out[name] = {
                **entry,
                **replacement.model_dump(mode="json"),
            }
            changed = True
    return out if changed else None
