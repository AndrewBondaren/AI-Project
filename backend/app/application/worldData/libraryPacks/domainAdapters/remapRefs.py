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

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.worldData.libraryPacks.domainAdapters.refFields import (
    LOCATION_TEMPLATE_REF_FIELDS, RELIEF_POLICY_REF_FIELDS,
    STRUCTURE_REF_FIELDS, structure_ref_model,
)
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.legacyDomainRefs import is_canonical_uid
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ReliefContextPickPolicy,
)
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.db.models.world import World
from app.ids import LibraryKind


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


def remap_named_location_refs(row: dict, uid_map: Mapping[str, str]) -> dict:
    """``named_locations`` row → remapped template refs (world copy, B4).

    Both persisted member refs follow the explicit copy map; uids absent
    from it (shared engine members, unrelated packs) stay untouched.
    """
    out = dict(row)
    for field in LOCATION_TEMPLATE_REF_FIELDS:
        ref = out.get(field)
        if isinstance(ref, str) and ref in uid_map:
            out[field] = uid_map[ref]
    return out


# Kinds a persisted location ref may legally point at; the legacy
# name→member conversion only searches these members (plan §2.4: the old
# building ref was a plot/body name, the structure ref a structure).
_LOCATION_REF_KINDS: dict[str, tuple[LibraryKind, ...]] = {
    "system_template_uid": (LibraryKind.PLOT_TEMPLATES, LibraryKind.BUILDING_TEMPLATES),
    "system_structure_template_uid": (LibraryKind.STRUCTURE_TEMPLATES,),
}


def remap_locations_section(rows, uid_map: Mapping[str, str], sources) -> list[dict]:
    """Bundle ``locations[]`` rows → remapped member refs (B4).

    ``uid_map`` is the composed source→target member map of this import
    (writer item projections + the legacy migration plan). ``sources``
    are the ``WriteImportSource`` projections the same import writes —
    their ``local_uid`` set is the *explicit* old plot/body map: a
    non-UUID leftover is a legacy readable name, resolved only through
    it. One candidate wins; ambiguity is an import error; no match
    clears the ref to ``None`` (legacy rows whose identity is not
    recoverable, never a guessed name).
    """
    names: dict[tuple[str, str], set[str]] = {}
    for source in sources.values():
        for entry in source.members:
            target = uid_map.get(entry.member.template_uid, entry.member.template_uid)
            names.setdefault((entry.member.library_kind, entry.member.local_uid),
                             set()).add(target)
    out = []
    for index, raw in enumerate(rows):
        row = remap_named_location_refs(raw, uid_map)
        for field in LOCATION_TEMPLATE_REF_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or is_canonical_uid(value):
                continue
            candidates = {uid for kind in _LOCATION_REF_KINDS.get(field, ())
                          for uid in names.get((kind.value, value), ())}
            if len(candidates) > 1:
                raise ImportValidationError([FieldPathError(
                    (BundleSection.LOCATIONS, index, field),
                    f"ambiguous legacy template name; candidates={sorted(candidates)}",
                    code="LEGACY_REF_AMBIGUOUS")])
            row[field] = next(iter(candidates)) if candidates else None
        out.append(row)
    return out


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
