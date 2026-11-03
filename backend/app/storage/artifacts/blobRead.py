"""Bounded read of an immutable file at a backend-validated path."""
import hashlib
from pathlib import Path

from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef


def read_verified_file(path: Path, ref: ArtifactRef) -> bytes:
    content = bytearray()
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        while len(content) < ref.nbytes:
            chunk = stream.read(min(1024 * 1024, ref.nbytes - len(content)))
            if not chunk:
                raise PublicationInfrastructureError("artifact shorter than descriptor")
            digest.update(chunk)
            content.extend(chunk)
        if stream.read(1) or digest.hexdigest() != ref.content_hash:
            raise PublicationInfrastructureError("artifact size or digest mismatch")
    return bytes(content)
