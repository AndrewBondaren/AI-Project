"""Raw legacy-world extraction before normalization. No repositories or mutation."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.libraryPacks.legacyDomainContracts import LEGACY_PLOT_FIELDS, LegacyDomainShape, SourcePath
from app.application.worldData.libraryPacks.legacyDomainRefs import is_canonical_uid
from app.ids import LibraryKind

REGISTRY_KINDS = {"building_template_registry": LibraryKind.BUILDING_TEMPLATES,
                  "relief_template_registry": LibraryKind.RELIEF_TEMPLATES}
TEMPLATE_KINDS = (LibraryKind.PLOT_TEMPLATES, LibraryKind.BUILDING_TEMPLATES,
                  LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.RELIEF_TEMPLATES)


@dataclass(frozen=True)
class LegacyWorldPointer:
    template_uid: str
    source_kind: LibraryKind
    path: SourcePath
    raw: dict


@dataclass(frozen=True)
class LegacyWorldBody:
    source_kind: LibraryKind
    shape: LegacyDomainShape
    local_uid: str | None
    source_uid: str | None
    body: dict
    path: SourcePath
    source_file: str | None = None


@dataclass(frozen=True)
class LegacyWorldInput:
    raw_world: dict
    raw_sections: dict
    pointers: tuple[LegacyWorldPointer, ...]
    bodies: tuple[LegacyWorldBody, ...]
    issues: tuple[FieldPathError, ...]


def extract_legacy_world_input(raw_world: dict, body_sections: Mapping | None = None) -> LegacyWorldInput:
    world, sections = deepcopy(raw_world), deepcopy(dict(body_sections or {}))
    pointers, bodies, issues = [], [], []
    if not isinstance(world, dict) or not isinstance(world.get("world_uid"), str) or not world["world_uid"]:
        return LegacyWorldInput(world, sections, (), (),
            (FieldPathError(("world", "world_uid"), "world_uid is required", code="STRICT_REQUIRED"),))

    def body(raw, kind, path, source_uid=None):
        if not isinstance(raw, dict) or not isinstance(raw.get("system_name"), str):
            issues.append(FieldPathError(path, "raw body requires system_name", code="STRICT_REQUIRED"))
            return
        shape = LegacyDomainShape.MODERN
        if kind == LibraryKind.PLOT_TEMPLATES or kind == LibraryKind.BUILDING_TEMPLATES and any(k in raw for k in LEGACY_PLOT_FIELDS):
            shape = LegacyDomainShape.PLOT
        elif kind == LibraryKind.BUILDING_TEMPLATES:
            shape = LegacyDomainShape.BUILDING_OUTLINE
        source = source_uid if source_uid is not None else raw.get("template_uid")
        if kind == LibraryKind.STRUCTURE_TEMPLATES and source is None:
            source = raw["system_name"]
        if source is not None and not is_canonical_uid(source):
            issues.append(FieldPathError(path + ("template_uid",), "source identity must be a UUID", code="TEMPLATE_UID"))
        key = raw.get("local_uid") if kind == LibraryKind.STRUCTURE_TEMPLATES else raw["system_name"]
        wire = {k: v for k, v in raw.items() if k not in ("template_uid", "local_uid", "source_file")}
        bodies.append(LegacyWorldBody(kind, shape, key, source, wire, path, raw.get("source_file")))

    for field, kind in REGISTRY_KINDS.items():
        rows = world.get(field, [])
        if not isinstance(rows, list):
            issues.append(FieldPathError(("world", field), "expected list", code="EXPECTED_LIST"))
            continue
        for index, row in enumerate(rows):
            path = ("world", field, index)
            if not isinstance(row, dict):
                issues.append(FieldPathError(path, "expected object", code="EXPECTED_OBJECT"))
                continue
            if "system_template_uid" in row:
                uid = row["system_template_uid"]
                if not is_canonical_uid(uid):
                    issues.append(FieldPathError(path + ("system_template_uid",), "pointer must be a UUID", code="TEMPLATE_UID"))
                    continue
                pointers.append(LegacyWorldPointer(uid, kind, path, row))
                if "body" in row:
                    body(row["body"], kind, path + ("body",), uid)
                elif "system_name" in row:
                    body({k: v for k, v in row.items() if k not in
                        ("system_template_uid", "display_template_name", "imported_at")}, kind, path, uid)
            else:
                body(row, kind, path)
    for kind in TEMPLATE_KINDS:
        rows = sections.get(kind.value, [])
        if not isinstance(rows, list):
            issues.append(FieldPathError((kind.value,), "expected list", code="EXPECTED_LIST"))
            continue
        for index, row in enumerate(rows):
            body(row, kind, (kind.value, index))
    return LegacyWorldInput(world, sections, tuple(pointers), tuple(bodies), tuple(issues))
