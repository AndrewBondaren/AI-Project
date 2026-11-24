"""Canonical descriptor preparation for one fixed content format."""

from pydantic import BaseModel, TypeAdapter

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.errors import ArtifactCodecError
from app.application.artifacts.staging.stageErrors import ArtifactInputRejected
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.staging.preparedArtifact import PreparedArtifact
from app.dataModel.artifacts.staging.inputErrors import ArtifactInputError, ArtifactInputIssue, ArtifactInputIssueCode
from app.dataModel.fields.validatedFieldPath import FieldSegment, ModelIdentity, ValidatedFieldPath
from app.dataModel.patch.values import FormatVersion
from app.encoding.canonicalCodec import content_digest


class ArtifactDescriptorBuilder[C: bytes | BaseModel]:
    def __init__(self, contract: ArtifactFormatContract[C], version: FormatVersion,
                 registry: ArtifactFormatRegistryBinding) -> None:
        registry.resolve(contract)
        version = TypeAdapter(FormatVersion).validate_python(version, strict=True)
        if version not in contract.supported_versions:
            raise ValueError("unsupported artifact version")
        self._contract, self._version, self._registry = contract, version, registry

    def build(self, content: C) -> ArtifactRef:
        try:
            data = self._registry.encode(self._contract, content)
            rows = None if self._contract.row_count is None else self._contract.row_count(content)
            if rows is not None and (type(rows) is not int or rows < 0):
                raise ValueError("invalid artifact row count")
        except Exception as error:
            raise ArtifactCodecError("artifact codec failed") from error
        return ArtifactRef(kind=self._contract.kind, format_key=self._contract.key,
            format_version=self._version, content_hash=content_digest(data).hex(),
            nbytes=len(data), row_count=rows)

    def prepare(self, content: C) -> PreparedArtifact[C]:
        return PreparedArtifact[self._contract.content_model](content=content, descriptor=self.build(content))

    def check(self, prepared: PreparedArtifact[C]) -> None:
        if self.build(prepared.content) != prepared.descriptor:
            owner = ModelIdentity(module=PreparedArtifact.__module__, qualname=PreparedArtifact.__qualname__)
            path = ValidatedFieldPath(root=owner, segments=(FieldSegment(owner=owner, name="descriptor"),))
            raise ArtifactInputRejected(ArtifactInputError(issues=(ArtifactInputIssue(
                code=ArtifactInputIssueCode.DESCRIPTOR_MISMATCH, path=path,
                message="prepared artifact descriptor differs from content"),)))
