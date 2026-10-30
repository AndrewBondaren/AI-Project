"""Pure strict scalar and wire validation at the SQLite boundary."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictInt, TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex

_UID = TypeAdapter(EntityUid)
_HASH = TypeAdapter(RevisionHex)
_POS = TypeAdapter(Annotated[StrictInt, Field(ge=1)])


def _fields(row: Mapping, *, uids=(), optional_uids=(), positives=(), hashes=(), optional_hashes=(), booleans=()) -> None:
    try:
        for key in uids:
            _UID.validate_python(row[key], strict=True)
        for key in optional_uids:
            if row[key] is not None:
                _UID.validate_python(row[key], strict=True)
        for key in positives:
            _POS.validate_python(row[key], strict=True)
        for key in hashes:
            _HASH.validate_python(row[key], strict=True)
        for key in optional_hashes:
            if row[key] is not None:
                _HASH.validate_python(row[key], strict=True)
        for key in booleans:
            if type(row[key]) is not int or row[key] not in (0, 1):
                raise ValueError("raw SQL boolean must be integer 0/1")
    except (ValueError, TypeError, KeyError) as error:
        raise PublicationInfrastructureError("invalid persisted scalar") from error


def _wire[E: StrEnum](kind: type[E], value: object) -> E:
    if type(value) is not str:
        raise PublicationInfrastructureError("SQL enum must be a wire string")
    try:
        return kind(value)
    except ValueError as error:
        raise PublicationInfrastructureError("unknown stored enum") from error


