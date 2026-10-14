"""Pure declared legacy-domain conversion; no SQL, fallback or implicit extraction."""
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace

from pydantic import BaseModel, ValidationError

from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import TemplatePreparationError
from app.application.worldData.libraryPacks.domainAdapters.building import BuildingBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.plot import PlotBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.structure import StructureBodyPreparation
from app.application.worldData.libraryPacks.domainAdapters.refFields import BUILDING_STRUCTURE_REF, STRUCTURE_REF_FIELDS
from app.application.worldData.libraryPacks.legacyDomainContracts import (
    ConvertedDomainRecord, EmbeddedBodyPath, LegacyDomainProvenance, LegacyDomainRecord,
    LegacyDomainShape, LegacyDomainSplitResult, LegacyReferenceResolution,
)
from app.application.worldData.libraryPacks.legacyDomainRefs import LegacyDomainRefResolver, is_canonical_uid
from app.application.worldData.libraryPacks.uidMap import compose_template_uid_maps
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind

_PREPARATIONS = {p.library_kind: p() for p in (
    PlotBodyPreparation, BuildingBodyPreparation, StructureBodyPreparation)}


def _record_issues(record):
    member, path = record.member, record.path
    issues = []
    if not isinstance(record.body, dict):
        issues.append(FieldPathError(path, "template body must be a raw JSON object", code="EXPECTED_OBJECT"))
    try:
        kind = LibraryKind(member.library_kind)
    except (ValueError, TypeError):
        kind = None
    expected = {LegacyDomainShape.PLOT: LibraryKind.PLOT_TEMPLATES,
                LegacyDomainShape.BUILDING_OUTLINE: LibraryKind.BUILDING_TEMPLATES}.get(record.shape)
    if (kind not in _PREPARATIONS or
        record.shape not in tuple(LegacyDomainShape) or
        expected is not None and kind != expected or
        record.shape == LegacyDomainShape.MODERN and record.source_kind != kind or
        record.shape != LegacyDomainShape.MODERN and record.source_kind not in
            (LibraryKind.BUILDING_TEMPLATES, expected)):
        issues.append(FieldPathError(path, "declared source shape/domain does not match destination kind",
                                     code="LEGACY_DOMAIN_KIND"))
    for label, uid in (("template_uid", member.template_uid), ("pack_uid", member.pack_uid),
                       ("source_uid", record.source_uid), ("source_template_uid", member.source_template_uid)):
        if (uid is not None or label in ("template_uid", "pack_uid")) and not is_canonical_uid(uid):
            issues.append(FieldPathError(path + (label,), "identity must be a canonical UUID", code="TEMPLATE_UID"))
    if (not isinstance(member.local_uid, str) or not member.local_uid or
        member.local_uid != member.local_uid.strip() or "|" in member.local_uid):
        issues.append(FieldPathError(path + ("local_uid",), "invalid declared local key", code="LEGACY_IDENTITY"))
    if (member.creation_kind not in ("authored", "pack_copy", "member_copy") or
        (member.creation_kind == "authored") != (member.source_template_uid is None)):
        issues.append(FieldPathError(path, "invalid declared provenance", code="LEGACY_PROVENANCE"))
    return issues


def _unsupported_fields(record, preparation):
    if record.shape == LegacyDomainShape.MODERN or not isinstance(record.body, dict):
        return []
    return [FieldPathError(record.path + (key,), "legacy field has no declared target mapping",
                             code="LEGACY_FIELD_UNREPRESENTABLE")
              for key in sorted(set(record.body) - preparation.model.model_fields.keys())]


def _wire_refs(payload, kind, mapping):
    """Preserve raw extension fields of modern bodies while remapping declared refs."""
    result = deepcopy(payload)
    if kind == LibraryKind.BUILDING_TEMPLATES:
        key = BUILDING_STRUCTURE_REF.uid_field
        if key in result:
            result[key] = mapping.get(result[key], result[key])
    elif kind == LibraryKind.PLOT_TEMPLATES:
        for field in STRUCTURE_REF_FIELDS:
            value = result.get(field.parent_field)
            entries = value if field.repeated and isinstance(value, list) else (value,)
            for body in entries:
                if isinstance(body, dict) and field.uid_field in body:
                    body[field.uid_field] = mapping.get(body[field.uid_field], body[field.uid_field])
    return result


def _nested_unsupported(raw, typed, path):
    issues = []
    if isinstance(raw, dict) and isinstance(typed, BaseModel):
        fields = type(typed).model_fields
        issues.extend(FieldPathError(path + (key,), "legacy nested field has no declared target mapping",
            code="LEGACY_FIELD_UNREPRESENTABLE") for key in sorted(set(raw) - fields.keys()))
        for key in raw.keys() & fields.keys():
            issues.extend(_nested_unsupported(raw[key], getattr(typed, key), path + (key,)))
    elif isinstance(raw, list) and isinstance(typed, list):
        for index, (source, value) in enumerate(zip(raw, typed)):
            issues.extend(_nested_unsupported(source, value, path + (index,)))
    return issues


def _convert(record, resolver):
    kind = LibraryKind(record.member.library_kind)
    preparation = _PREPARATIONS[kind]
    issues = _unsupported_fields(record, preparation)
    if issues:
        return None, issues
    payload = deepcopy(record.body)
    if kind == LibraryKind.STRUCTURE_TEMPLATES and isinstance(payload, dict):
        source = payload.get("system_name", record.member.template_uid)
        if not is_canonical_uid(source) or source not in (record.source_uid, record.member.template_uid):
            return None, [FieldPathError(record.path + ("system_name",),
                "structure body identity does not match declared source/destination", code="LEGACY_IDENTITY")]
        payload["system_name"] = record.member.template_uid
    try:
        typed = preparation.model.model_validate(payload)
    except ValidationError as exc:
        return None, [FieldPathError(record.path + tuple(error["loc"]), error["msg"], code=error["type"])
                      for error in exc.errors()]
    if record.shape != LegacyDomainShape.MODERN:
        issues.extend(_nested_unsupported(payload, typed, record.path))
        if issues:
            return None, issues
    references, ref_map = [], {}
    for ref in preparation.body_refs(typed, record.member.template_uid):
        path = record.path + (ref.path,)
        target, issue = resolver.resolve(LibraryKind(ref.library_kind), ref.template_uid,
            path, allow_name=record.shape != LegacyDomainShape.MODERN)
        if issue:
            issues.append(issue)
        else:
            ref_map[ref.template_uid] = target
            if target != ref.template_uid:
                references.append(LegacyReferenceResolution(path, LibraryKind(ref.library_kind), ref.template_uid, target))
    if issues:
        return None, issues
    remapped = preparation.remap_body(typed, ref_map)
    try:
        prepared = preparation.prepare_body(remapped.model_dump(mode="json"),
            local_uid=record.member.local_uid, template_uid=record.member.template_uid)
    except TemplatePreparationError as exc:
        return None, [replace(issue, path=record.path + issue.path[2:]) for issue in exc.issues]
    wire = (_wire_refs(payload, kind, ref_map) if record.shape == LegacyDomainShape.MODERN
            else prepared.model_dump(mode="json"))
    embedded = ()
    if kind == LibraryKind.PLOT_TEMPLATES:
        embedded = tuple(EmbeddedBodyPath(record.path + (field.parent_field,) +
            ((index,) if field.repeated else ()), record.member.template_uid)
            for field in STRUCTURE_REF_FIELDS
            for index, _ in enumerate(tuple(field.entries(prepared))))
    provenance = LegacyDomainProvenance(record.source_uid, record.member.template_uid,
                                        record.source_kind, kind, record.path)
    return ConvertedDomainRecord(deepcopy(record.member), wire, prepared, provenance, embedded,
                                 tuple(references), record.source_file), []


def split_legacy_domains(
    records: Sequence[LegacyDomainRecord], *, available_members: Sequence[LibraryPackMemberRow] = (),
    uid_maps: Sequence[Mapping[str, str]] = (),
    name_map: Mapping[tuple[LibraryKind, str], str] | None = None,
) -> LegacyDomainSplitResult:
    """All-or-error conversion; inputs and originals remain detached and unchanged.

    Availability/owner is already scoped by the caller. UID stages may compose
    old → engine → world; names resolve only at this compatibility boundary.
    """
    sources = deepcopy(tuple(records))
    issues = [issue for record in sources for issue in _record_issues(record)]
    for (kind, name), uid in (name_map or {}).items():
        if not is_canonical_uid(uid):
            issues.append(FieldPathError(("name_map", str(kind), name),
                "explicit name mapping must target a canonical UUID", code="LEGACY_UID_MAP"))
    edges, members = {}, {}
    for member in deepcopy(tuple(available_members)) + tuple(r.member for r in sources):
        previous = members.get(member.template_uid)
        if previous is not None and previous != member:
            issues.append(FieldPathError(("members", member.template_uid),
                "conflicting scoped membership", code="LEGACY_IDENTITY"))
        members[member.template_uid] = member
    seen = set()
    for record in sources:
        uid = record.member.template_uid
        if uid in seen:
            issues.append(FieldPathError(record.path, "duplicate destination UID", code="LEGACY_IDENTITY"))
        seen.add(uid)
        if record.source_uid is not None:
            if record.source_uid in edges and edges[record.source_uid] != uid:
                issues.append(FieldPathError(record.path, "one source UID has multiple destinations", code="LEGACY_UID_MAP"))
            edges[record.source_uid] = uid
    try:
        for mapping in (*uid_maps, edges):
            if any(not is_canonical_uid(a) or not is_canonical_uid(b) for a, b in mapping.items()):
                raise ValueError("UID mappings must contain canonical UUID identities")
        mapping = compose_template_uid_maps(*uid_maps, edges)
        for record in sources:
            if mapping.get(record.member.template_uid, record.member.template_uid) != record.member.template_uid:
                raise ValueError("destination member must carry its final composed UID")
    except ValueError as exc:
        issues.append(FieldPathError(("uid_map",), str(exc), code="LEGACY_UID_MAP"))
        mapping = {}
    converted = []
    if not issues:
        resolver = LegacyDomainRefResolver(tuple(members.values()), mapping, name_map or {})
        for record in sources:
            value, errors = _convert(record, resolver)
            issues.extend(errors)
            if value is not None:
                converted.append(value)
    return LegacyDomainSplitResult(sources, tuple(converted) if not issues else (),
                                   tuple(sorted(mapping.items())) if not issues else (), tuple(issues))
