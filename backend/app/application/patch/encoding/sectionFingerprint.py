"""Fingerprint the full owning section representation through its checked codec."""

from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.encoding.canonicalCodec import content_digest


class SectionFingerprint:
    def __init__(self, registry: SectionRegistry) -> None:
        self._registry = registry

    def fingerprint(self, section: DomainSection) -> RevisionHex:
        return content_digest(self._registry.resolve_codec(section).encode(section)).hex()
