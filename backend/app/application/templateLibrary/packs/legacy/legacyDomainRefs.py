"""Pure compatibility reference resolution against supplied scoped membership."""
from collections.abc import Mapping, Sequence
from uuid import UUID

from app.application.jsonValidation.types import FieldPathError
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind


def is_canonical_uid(value) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


class LegacyDomainRefResolver:
    def __init__(self, members: Sequence[LibraryPackMemberRow], uid_map: Mapping[str, str],
                 names: Mapping[tuple[LibraryKind, str], str]):
        self._members = {member.template_uid: member for member in members}
        self._uid_map, self._names = uid_map, names

    def resolve(self, kind: LibraryKind, token: str, path: tuple, *, allow_name: bool):
        explicit = self._names.get((kind, token)) if allow_name else None
        if is_canonical_uid(token) or explicit is not None:
            uid = self._uid_map.get(explicit or token, explicit or token)
            member = self._members.get(uid)
            if member is not None and member.library_kind == kind.value:
                return uid, None
            code = "LEGACY_REF_KIND" if member is not None else "LEGACY_REF_UNAVAILABLE"
            return None, FieldPathError(path, f"unavailable {kind.value}:{uid}", code=code)
        if not allow_name:
            return None, FieldPathError(path, "modern template reference must be a UID", code="TEMPLATE_REF_UID")
        candidates = sorted({member.template_uid for member in self._members.values()
                             if member.library_kind == kind.value and member.local_uid == token})
        if len(candidates) == 1:
            return candidates[0], None
        return None, FieldPathError(path,
            f"legacy {kind.value} name {token!r}: candidates={candidates}",
            code="LEGACY_REF_AMBIGUOUS" if candidates else "LEGACY_REF_UNKNOWN")
