"""Public in-memory preparation and standalone staging entries."""

from pydantic import BaseModel

from app.application.artifacts.staging.artifactDescriptor import ArtifactDescriptorBuilder
from app.application.artifacts.staging.artifactStageWriter import ArtifactStageWriter
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInput, PreparedArtifact
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInput


class ArtifactPrepareStageOpenPipeline[C: bytes | BaseModel]:
    def __init__(self, admission: object, descriptors: ArtifactDescriptorBuilder[C]) -> None:
        self._admission, self._descriptors = admission, descriptors

    def prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]:
        request = self._admission.prepare(request)
        return self._descriptors.prepare(request.content)


class ArtifactStageOpenPipeline[C: bytes | BaseModel]:
    def __init__(self, admission: object, descriptors: ArtifactDescriptorBuilder[C],
                 writer: ArtifactStageWriter[C]) -> None:
        self._admission, self._descriptors, self._writer = admission, descriptors, writer

    async def stage(self, request: ArtifactStageInput[C]) -> ArtifactRef:
        request = self._admission.stage(request)
        self._descriptors.check(request.prepared)
        return await self._writer.write(request.lease, request.prepared)
