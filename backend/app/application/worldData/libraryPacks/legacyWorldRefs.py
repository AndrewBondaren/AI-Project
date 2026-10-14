"""Declared world ref projection, retaining raw registries for later extraction/cutover."""
from copy import deepcopy

from pydantic import ValidationError

from app.application.jsonValidation.types import FieldPathError, ImportValidationError, ReferenceIssueContext, ReferenceIssueReason
from app.application.worldData.libraryPacks.domainAdapters.refFields import RELIEF_POLICY_REF_FIELDS
from app.application.worldData.libraryPacks.legacyDomainRefs import is_canonical_uid
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.ids import LibraryKind


def project_world_refs(world, mapping, members, pointer_pins):
    projected = deepcopy(world)
    pins = {(p.library_kind, p.template_uid): p for p in pointer_pins}
    diagnostics = []
    raw_pins = world.get("library_pins", [])
    if not isinstance(raw_pins, list):
        raise ImportValidationError([FieldPathError(("world", "library_pins"), "expected list", code="EXPECTED_LIST")])
    for index, raw in enumerate(raw_pins):
        try:
            pin = LibraryPinEntry.model_validate(raw)
        except ValidationError as exc:
            raise ImportValidationError([FieldPathError(("world", "library_pins", index) + tuple(e["loc"]),
                e["msg"], code=e["type"]) for e in exc.errors()]) from exc
        if not is_canonical_uid(pin.template_uid):
            raise ImportValidationError([FieldPathError(("world", "library_pins", index, "template_uid"),
                "pin identity must be a UUID", code="TEMPLATE_UID")])
        uid = mapping.get(pin.template_uid, pin.template_uid)
        member = members.get(uid)
        if member is not None:
            # Explicit migration may change the old mixed building kind to plot.
            if member.library_kind != pin.library_kind and not (
                pin.library_kind == LibraryKind.BUILDING_TEMPLATES.value and member.library_kind == LibraryKind.PLOT_TEMPLATES.value):
                raise ImportValidationError([FieldPathError(("world", "library_pins", index),
                    "pin kind does not match migrated member", code="LIBRARY_REFERENCE")])
            pin = LibraryPinEntry(library_kind=member.library_kind, template_uid=uid)
        else:
            diagnostics.append(FieldPathError(("world", "library_pins", index),
                "existing pin is unavailable; original pair retained", code="LIBRARY_REFERENCE",
                reference=ReferenceIssueContext(ReferenceIssueReason.UNKNOWN_TEMPLATE, pin.library_kind,
                    world["world_uid"], pin.template_uid, consumer=f"world:{world['world_uid']}")))
        pins[pin.library_kind, pin.template_uid] = pin
    ordered = tuple(pins[key] for key in sorted(pins))
    projected["library_pins"] = [pin.model_dump(mode="json") for pin in ordered]
    raw_policy = projected.get("relief_pick_policy")
    if raw_policy is not None:
        if not isinstance(raw_policy, dict):
            raise ImportValidationError([FieldPathError(("world", "relief_pick_policy"), "expected object", code="EXPECTED_OBJECT")])
        for field in RELIEF_POLICY_REF_FIELDS:
            if field.parent_field not in raw_policy:
                continue
            path = ("world", "relief_pick_policy", field.parent_field)
            try:
                policy = ReliefContextPickPolicy.model_validate(raw_policy[field.parent_field])
            except ValidationError as exc:
                raise ImportValidationError([FieldPathError(path + tuple(e["loc"]), e["msg"], code=e["type"])
                                             for e in exc.errors()]) from exc
            replacement = field.remap_entry(policy, mapping)
            if replacement is not policy:
                raw_policy[field.parent_field] = {**raw_policy[field.parent_field],
                                                 **replacement.model_dump(mode="json")}
    return projected, ordered, tuple(diagnostics)
