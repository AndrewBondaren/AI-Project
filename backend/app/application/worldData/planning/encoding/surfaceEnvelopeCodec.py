"""Typed surface envelope admission using the public immutable-data boundary."""

from dataclasses import dataclass
from pydantic import TypeAdapter
from app.application.cache.service.cacheService import retained_entry_bytes, validate_immutable
from app.application.encoding.canonicalCodec import encode, decode
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope


@dataclass(frozen=True)
class SurfaceEnvelopeCodec[T]:
    envelope_type: type[PlanEnvelope[T]]
    manifest: CanonicalSchemaManifest

    def validate(self, value: object) -> PlanEnvelope[T]:
        # The engine builds a generic envelope. Admit its complete object graph,
        # then bind T before canonical encoding checks every nested field.
        validate_immutable(value)
        envelope = TypeAdapter(self.envelope_type).validate_python(value, strict=True)
        encode(envelope, self.manifest)
        return envelope

    def encode(self, value: PlanEnvelope[T]) -> bytes:
        return encode(self.validate(value), self.manifest)

    def decode(self, encoded: bytes) -> PlanEnvelope[T]:
        return self.validate(decode(encoded, self.envelope_type, self.manifest))

    def retained_bytes(self, value: PlanEnvelope[T]) -> int:
        return retained_entry_bytes(value)


