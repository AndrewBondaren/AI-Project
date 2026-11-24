"""Versioned canonical tuple projection; domain section codecs own their payloads."""

from dataclasses import dataclass
from typing import ClassVar, Union, get_args, get_origin
from types import UnionType
from pydantic import TypeAdapter, ValidationError
from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.fields.validatedFieldPath import ModelIdentity, is_model_identity_owner
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.validation.modelContractChecks import ModelContractChecks
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.patch.validation.admissionReasons import (
    PatchSetAdmissionReason, ADMISSION_REASON_TYPES, PatchSetRequestModelMismatch, PatchSetRequestVersionUnsupported,
)
from app.application.patch.errors import PatchSetAdmissionError
from app.application.patch.validation.modelValidationErrors import PatchSetModelValidationErrors

from app.encoding.canonicalCodec import (
    CanonicalEncodingError, content_digest, decode as canonical_decode, encode as canonical_encode,
)
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation


@dataclass(frozen=True, slots=True)
class PatchSetCodec[S: DomainSection]:
    registry: SectionRegistry
    request_model: type[PatchSet[S]]
    SUPPORTED_VERSIONS: ClassVar[frozenset[FormatVersion]] = frozenset({1})

    def __post_init__(self) -> None:
        self.validate_configuration()

    def validate_configuration(self) -> None:
        model = self.request_model
        if not is_model_identity_owner(model) or not issubclass(model, PatchSet):
            raise TypeError("codec requires a named closed PatchSet model")
        if not ModelContractChecks.same_validation_config(model.model_config, PatchSet.model_config):
            raise TypeError("request model must retain strict immutable validation")
        sections_name = bind_field(FieldRef(lambda: PatchSet, lambda value: value.sections)).field
        if tuple(model.model_fields) != tuple(PatchSet.model_fields):
            raise TypeError("request model must retain PatchSet fields")
        for name, field in PatchSet.model_fields.items():
            actual = model.model_fields[name]
            if (not actual.is_required() or actual.metadata != field.metadata
                    or name != sections_name and actual.annotation != field.annotation):
                raise TypeError("request model must retain field constraints")
        if not ModelContractChecks.same_validators(model, PatchSet):
            raise TypeError("request model must retain PatchSet validators")
        annotation = model.model_fields[sections_name].annotation
        args = get_args(annotation)
        if get_origin(annotation) is not tuple or len(args) != 2 or args[1] is not Ellipsis:
            raise TypeError("sections must be an ordered tuple")
        member = unwrap_wire_type(args[0])
        members = get_args(member) if get_origin(member) in (Union, UnionType) else (member,)
        if any(not is_model_identity_owner(item) or not issubclass(item, DomainSection) for item in members):
            raise TypeError("sections must bind named native models")
        if not frozenset(members) <= self.registry.section_models:
            raise ValueError("request section models are not registered")

    def validate_request(self, request: PatchSet[S]) -> PatchSet[S]:
        if type(request) is not self.request_model:
            raise PatchSetAdmissionError((PatchSetRequestModelMismatch(
                expected_model=ModelIdentity.of(self.request_model),
                actual_type_name=f"{type(request).__module__}.{type(request).__qualname__}"),))
        try:
            request = self.request_model.model_validate(request, strict=True)
        except ValidationError as error:
            raise PatchSetAdmissionError(PatchSetModelValidationErrors.classify(error)) from error
        errors = ValidatorAggregationHelper[PatchSetAdmissionReason](ADMISSION_REASON_TYPES)
        if request.format_version not in self.SUPPORTED_VERSIONS:
            errors.add(PatchSetRequestVersionUnsupported(code="patch_set.admission.request_version_unsupported",
                actual_version=request.format_version, supported_versions=tuple(sorted(self.SUPPORTED_VERSIONS))))
        for index, section in enumerate(request.sections):
            for issue in self.registry.admission_issues(section, section_index=index):
                errors.add(issue)
        errors.raise_if_any(PatchSetAdmissionError)
        return request

    def encode(self, request: PatchSet[S]) -> bytes:
        request = self.validate_request(request)
        fields: list[tuple[str, object]] = []
        for name in self.request_model.model_fields:
            value = getattr(request, name)
            if name == "sections":
                value = tuple((section.header.key, section.header.format_version,
                               self.registry.resolve_codec(section).encode(section)) for section in request.sections)
            elif name == "expected_players":
                value = tuple(sorted(request.expected_players, key=lambda player: player.player_uid))
            fields.append((name, value))
        return canonical_encode((request.format_version, tuple(fields)), self.registry.manifest)

    def decode(self, payload: bytes) -> PatchSet[S]:
        projection = canonical_decode(payload, tuple, self.registry.manifest)
        if (len(projection) != 2 or type(projection[0]) is not int
                or projection[0] not in self.SUPPORTED_VERSIONS or type(projection[1]) is not tuple):
            raise CanonicalEncodingError("unsupported or invalid PatchSet projection")
        pairs = projection[1]
        if any(type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str for pair in pairs):
            raise CanonicalEncodingError("invalid PatchSet field pairs")
        if tuple(pair[0] for pair in pairs) != tuple(self.request_model.model_fields):
            raise CanonicalEncodingError("missing, extra, duplicate or reordered PatchSet fields")
        values = dict(pairs)
        if type(values["format_version"]) is not int or values["format_version"] != projection[0]:
            raise CanonicalEncodingError("PatchSet version does not match its projection")
        players = TypeAdapter(tuple[PlayerHeadExpectation, ...]).validate_python(values["expected_players"], strict=True)
        if players != tuple(sorted(players, key=lambda player: player.player_uid)):
            raise CanonicalEncodingError("player expectations are not in canonical UID order")
        sections = values["sections"]
        if type(sections) is not tuple:
            raise CanonicalEncodingError("section projection must be an ordered tuple")
        keys: set[SectionKey] = set()
        # Complete structural/registry preflight before calling any domain decoder.
        for section in sections:
            if (type(section) is not tuple or len(section) != 3 or type(section[1]) is not int
                    or type(section[2]) is not bytes):
                raise CanonicalEncodingError("invalid section projection")
            key = TypeAdapter(SectionKey).validate_python(section[0], strict=True)
            bound = self.registry.require_codec(key)
            if key in keys or section[1] not in bound.metadata.supported_versions:
                raise CanonicalEncodingError("duplicate section or unsupported section version")
            keys.add(key)
        decoded = []
        for key, version, content in sections:
            section = self.registry.require_codec(key).decode(content, version)
            if section.header.key != key:
                raise CanonicalEncodingError("decoded section key does not match its projection")
            decoded.append(section)
        values["sections"] = tuple(decoded)
        return self.request_model.model_validate(values, strict=True)

    def fingerprint(self, request: PatchSet[S]) -> RevisionHex:
        return content_digest(self.encode(request)).hex()

    def fingerprint_bytes(self, payload: bytes) -> RevisionHex:
        # Validation may read-upgrade sections; binding remains the original stored bytes.
        self.decode(payload)
        return content_digest(payload).hex()
