"""Bounded physical read capability for immutable BLOB backends."""
from abc import abstractmethod

from app.application.artifacts.contracts.formatBackend import ArtifactBackend
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef


class CorruptBlobError(PublicationInfrastructureError):
    """Physical content differs from the descriptor."""


class ReadableBlobBackend(ArtifactBackend[bytes]):
    @abstractmethod
    async def read_verified(self, ref: ArtifactRef, *, max_bytes: int) -> bytes:
        """Return only the bytes matching the admitted size and SHA-256."""
        ...
