"""Strict historical binding codec; decoding does not attest live authority."""
from app.application.publication.encoding.preparationSourceManifest import PREPARATION_SOURCE_ENCODING
from app.application.publication.validation.preparationSourceBindingValidator import PreparationSourceBindingValidator
from app.dataModel.publication.preparationSourceAuthority import PreparationSourceBinding
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.encoding.canonicalCodec import CanonicalEncodingError, decode, encode


class PreparationSourceBindingCodec:
    def _validate(self, value: PreparationSourceBinding) -> None:
        issues = PreparationSourceBindingValidator().validate(value)
        if issues:
            # Preserve concrete diagnostics, including paths, for the storage cause.
            raise CanonicalEncodingError(issues)

    def encode(self, value: PreparationSourceBinding) -> bytes:
        self._validate(value)
        return encode(value, PREPARATION_SOURCE_ENCODING)

    def decode(self, payload: bytes) -> PreparationSourceBinding:
        value = decode(payload, PreparationSourceBinding, PREPARATION_SOURCE_ENCODING)
        self._validate(value)
        return value

    def encode_request(self, value: SourceProofReadInput) -> bytes:
        value = SourceProofReadInput.model_validate(value, strict=True)
        return encode(value, PREPARATION_SOURCE_ENCODING)
