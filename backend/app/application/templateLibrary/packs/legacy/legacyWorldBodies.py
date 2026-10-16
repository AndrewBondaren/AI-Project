"""Pure body preparation/comparison/remap, shared by B1 classification and projection."""
from copy import deepcopy
from dataclasses import replace

from pydantic import ValidationError

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.templateLibrary.packs.legacy.legacyDomainContracts import LegacyDomainRecord, LegacyDomainShape
from app.application.templateLibrary.packs.legacy.legacyDomainSplit import split_legacy_domains
from app.application.templateLibrary.packs.write.writeInspectionContracts import WriteImportMember
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.ids import LibraryKind


def _with_extensions(raw, prepared):
    """Canonicalize known values/defaults without losing modern raw extensions."""
    if isinstance(raw, dict) and isinstance(prepared, dict):
        return {**deepcopy(raw), **{k: _with_extensions(raw.get(k), v) for k, v in prepared.items()}}
    if isinstance(raw, list) and isinstance(prepared, list):
        return [_with_extensions(raw[i] if i < len(raw) else None, v) for i, v in enumerate(prepared)]
    return deepcopy(prepared)


def target_kind(kind, shape):
    return LibraryKind.PLOT_TEMPLATES if shape == LegacyDomainShape.PLOT else LibraryKind(kind)


class LegacyWorldBodyTools:
    def __init__(self, facts, aliases):
        self.shapes = dict(facts.body_shapes)
        self.aliases = aliases
        self.members = {e.member.template_uid: replace(e.member,
            library_kind=target_kind(e.member.library_kind, self.shapes.get(e.member.template_uid)).value)
            for p in facts.packs for e in p.members}

    def prepare(self, member, raw, *, source_kind, shape, path, source_uid=None, source_file=None, mapping=None):
        kind = LibraryKind(member.library_kind)
        if kind == LibraryKind.RELIEF_TEMPLATES:
            try:
                body = ReliefTemplate.model_validate(raw)
            except ValidationError as exc:
                raise ImportValidationError([FieldPathError(path + tuple(e["loc"]), e["msg"], code=e["type"])
                                             for e in exc.errors()]) from exc
            if body.system_name != member.local_uid:
                raise ImportValidationError([FieldPathError(path + ("system_name",),
                    "body name does not match member local key", code="TEMPLATE_IDENTITY")])
            return WriteImportMember(deepcopy(member), _with_extensions(raw, body.model_dump(mode="json")), source_file)
        members = {**self.members, member.template_uid: member}
        if mapping is not None:
            # An old row and its projected row are one candidate after remap.
            members = {mapping.get(uid, uid): members.get(mapping.get(uid, uid), row)
                       for uid, row in members.items()}
        source_uid = source_uid or member.template_uid
        payload = deepcopy(raw)
        if kind == LibraryKind.STRUCTURE_TEMPLATES and isinstance(payload, dict):
            uid = payload.get("system_name")
            if isinstance(uid, str) and self.aliases.get(uid) == source_uid:
                payload["system_name"] = source_uid
        converted = split_legacy_domains((LegacyDomainRecord(member, source_kind, shape,
            payload, path, source_uid, source_file),), available_members=tuple(members.values()),
            uid_maps=(mapping if mapping is not None else self.aliases,)).require_valid()[0]
        return WriteImportMember(deepcopy(member),
            _with_extensions(converted.body, converted.prepared.model_dump(mode="json")), source_file)

    def normalize(self, entry):
        shape = self.shapes.get(entry.member.template_uid, LegacyDomainShape.MODERN)
        member = replace(entry.member, library_kind=target_kind(entry.member.library_kind, shape).value)
        return self.prepare(member, entry.body, source_kind=LibraryKind(entry.member.library_kind), shape=shape,
            path=("library_packs", entry.member.pack_uid, "members", entry.member.template_uid),
            source_uid=entry.member.template_uid, source_file=entry.source_file)

    def remap(self, entry, member, mapping, *, path=()):
        # Destination metadata may belong to a previously created instance.
        self.members[member.template_uid] = member
        return self.prepare(member, entry.body, source_kind=LibraryKind(entry.member.library_kind),
            shape=LegacyDomainShape.MODERN, path=path, source_uid=entry.member.template_uid,
            source_file=entry.source_file, mapping=mapping)
