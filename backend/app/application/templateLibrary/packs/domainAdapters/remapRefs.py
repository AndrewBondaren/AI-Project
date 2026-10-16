"""World-side / body ref remap helpers — TZ §2.

Entries that carry a declared ref field are remapped through their POJO
(``model_copy``) and the dump overlays the raw row so unknown keys
survive. Refs absent from ``uid_map`` — other packs, external bodies —
stay untouched.

Convention: helpers are pure return-new — they hand back the rewritten
value (``None`` / the input itself when nothing matched) and never
mutate arguments; the caller assigns the result.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.templateLibrary.packs.domainAdapters.refFields import (
    LOCATION_TEMPLATE_REF_FIELDS, LOCATION_TEMPLATE_REF_KINDS,
    RELIEF_POLICY_REF_FIELDS,
)
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.templateLibrary.packs.legacy.legacyDomainRefs import is_canonical_uid
from app.application.templateLibrary.packs.lifecycleContracts import RELIEF_POLICY_FIELD
from app.dataModel.terrain.relief.worldReliefPickPolicy import (
    ReliefContextPickPolicy,
)
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.db.models.world import World


def remap_pins(world: World, uid_map: Mapping[str, str]) -> list[dict] | None:
    """Remapped ``library_pins`` rows — ``None`` when no pin moved."""
    from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
    out = []
    changed = False
    for raw in world.library_pins or []:
        pin = LibraryPinEntry.model_validate(raw)
        uid = uid_map.get(pin.template_uid, pin.template_uid)
        changed = changed or uid != pin.template_uid
        out.append({**raw, 'template_uid': uid})
    return out if changed else None


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
            candidates = {uid for kind in LOCATION_TEMPLATE_REF_KINDS.get(field, ())
                          for uid in names.get((kind.value, value), ())}
            if len(candidates) > 1:
                raise ImportValidationError([FieldPathError(
                    (BundleSection.LOCATIONS, index, field),
                    f"ambiguous legacy template name; candidates={sorted(candidates)}",
                    code="LEGACY_REF_AMBIGUOUS")])
            row[field] = next(iter(candidates)) if candidates else None
        out.append(row)
    return out


def remap_relief_pick_policy(world: World, uid_map: Mapping[str, str]) -> dict | None:
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
                f"{RELIEF_POLICY_FIELD}.{name} fails schema during ref remap: {exc}"
            ) from exc
        replacement = field.remap_entry(policy, uid_map)
        if replacement is not policy:
            out[name] = {
                **entry,
                **replacement.model_dump(mode="json"),
            }
            changed = True
    return out if changed else None
