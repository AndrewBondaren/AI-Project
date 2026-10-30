"""Pure bytes/checksum verification before decoding."""

from app.application.encoding.canonicalCodec import content_digest
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.db.repositories.sqlite.shared.validation.rowValues import _HASH


def _checked_blob(data: bytes, checksum: RevisionHex) -> bytes:
    _HASH.validate_python(checksum, strict=True)
    if type(data) is not bytes or content_digest(data).hex() != checksum:
        raise PublicationInfrastructureError("stored bytes/checksum mismatch")
    return data
