"""Apply the configured manifest budget before opening a content-addressed BLOB."""
from pathlib import Path

from app.application.artifacts.storage.artifactLeases import IArtifactLeases
from app.application.worldData.pack.encoding.manifestFormat import manifest_format
from app.dataModel.artifacts.references import ArtifactRef
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend


class ManifestBlobBackend(ContentAddressedBlobBackend):
    def __init__(self, root: Path, leases: IArtifactLeases, *, max_bytes: int):
        super().__init__(root, manifest_format(max_bytes), leases)
        self._max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    async def read_verified(self, ref: ArtifactRef, *, max_bytes: int) -> bytes:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("manifest read requires a positive byte budget")
        return await super().read_verified(ref, max_bytes=min(max_bytes, self._max_bytes))
