"""Identity of a metadata projection; not provenance or a retention capability."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldPack.preparation.addresses import PackAssemblyAddress
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PackMetadataSubject(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    base_publication: WorldPublicationRef
    address: PackAssemblyAddress
    value_fingerprint: RevisionHex
