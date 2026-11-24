"""Infrastructure faults of artifact codecs and storage contracts."""

from app.application.publication.errors import PublicationInfrastructureError


class ArtifactCodecError(PublicationInfrastructureError):
    """The fixed codec failed or violated its declared output contract."""


class ArtifactDescriptorConflictError(PublicationInfrastructureError):
    """An existing content identity has a conflicting descriptor."""


class ArtifactStorageInvariantError(PublicationInfrastructureError):
    """Persisted state or a storage result violates an internal contract."""
