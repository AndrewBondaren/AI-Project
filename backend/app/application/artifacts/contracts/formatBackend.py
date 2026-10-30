"""Content-specific codecs and backends; no universal SQL row writer."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pydantic import BaseModel, TypeAdapter

from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactKind, ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import StagingReservation
from app.dataModel.patch.values import FormatVersion


@dataclass(frozen=True, slots=True)
class ArtifactFormatContract[C: bytes | BaseModel]:
    key: ArtifactFormatKey
    kind: ArtifactKind
    supported_versions: frozenset[FormatVersion]
    content_model: type[C]
    encode: Callable[[C], bytes]
    decode: Callable[[bytes, FormatVersion], C]

    def __post_init__(self) -> None:
        TypeAdapter(ArtifactFormatKey).validate_python(self.key, strict=True)
        TypeAdapter(ArtifactKind).validate_python(self.kind, strict=True)
        TypeAdapter(frozenset[FormatVersion]).validate_python(self.supported_versions, strict=True)
        if not self.supported_versions or not callable(self.encode) or not callable(self.decode):
            raise ValueError("artifact format needs versions and pure codecs")
        model = self.content_model
        if self.kind is ArtifactKind.BLOB:
            if model is not bytes:
                raise TypeError("BLOB content must be bytes")
        else:
            if not isinstance(model, type) or not issubclass(model, BaseModel) or model is BaseModel:
                raise TypeError("SQL_ROWS requires a concrete frozen row-set model")
            if (model.model_config.get("frozen") is not True or model.model_config.get("strict") is not True
                    or model.model_config.get("extra") != "forbid"
                    or model.model_config.get("revalidate_instances") != "always"
                    or model.__pydantic_generic_metadata__.get("parameters")):
                raise TypeError("row-set model must be concrete, frozen and strict")


class ArtifactBackend[C: bytes | BaseModel](ABC):
    @property
    @abstractmethod
    def contract(self) -> ArtifactFormatContract[C]: ...

    @abstractmethod
    async def write(self, reservation: StagingReservation, content: C) -> None:
        """Check reservation/fence before writing; never overwrite published content."""
        ...

    @abstractmethod
    async def verify(self, ref: ArtifactRef) -> None:
        """Check durable full content, descriptor and domain row projection."""
        ...

    @abstractmethod
    async def delete(self, ref: ArtifactRef) -> None:
        """Delete only while the caller holds the shared GC/holder/writer guard."""
        ...
