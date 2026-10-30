"""Versioned canonical tuple projection; domain section codecs own their payloads."""

from dataclasses import dataclass
from typing import ClassVar
from pydantic import TypeAdapter

from app.application.encoding.canonicalCodec import (
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

    def encode(self, request: PatchSet[S]) -> bytes:
        if type(request) is not self.request_model:
            raise CanonicalEncodingError("request must have the declared concrete PatchSet model")
        request = self.request_model.model_validate(request, strict=True)
        if request.format_version not in self.SUPPORTED_VERSIONS:
            raise CanonicalEncodingError("unsupported PatchSet format version")
        fields: list[tuple[str, object]] = []
        for name in self.request_model.model_fields:
            value = getattr(request, name)
            if name == "sections":
                value = tuple((section.header.key, section.header.format_version,
                               self.registry.resolve(section).encode(section)) for section in request.sections)
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
            bound = self.registry.require(key)
            if key in keys or section[1] not in bound.metadata.supported_versions:
                raise CanonicalEncodingError("duplicate section or unsupported section version")
            keys.add(key)
        decoded = []
        for key, version, content in sections:
            section = self.registry.require(key).decode(content, version)
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
