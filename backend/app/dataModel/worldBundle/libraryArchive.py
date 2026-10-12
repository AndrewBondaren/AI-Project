"""Lossless archive metadata; separate from the name-based FS author contract."""

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.ids import LibraryKind


LIBRARY_DOMAIN_ROOTS: Mapping[str, str] = MappingProxyType({
    LibraryKind.BUILDING_TEMPLATES: "building_templates",
    LibraryKind.STRUCTURE_TEMPLATES: "structures_templates",
    LibraryKind.RELIEF_TEMPLATES: "relief_templates",
    LibraryKind.RACE_TEMPLATES: "race_templates",
    LibraryKind.PERK_TEMPLATES: "perk_templates",
})
PACK_MANIFEST_FILE = "pack.manifest.json"


class LibraryArchiveMember(BaseModel):
    """Copied member identity is carried, never reconstructed from local_uid."""

    model_config = ConfigDict(extra="allow", frozen=True)

    library_kind: StrictOnWire[str]
    local_uid: StrictOnWire[str]
    template_uid: StrictOnWire[str]
    source_file: DefaultWhenMissing[str | None] = None
    source_template_uid: DefaultWhenMissing[str | None] = None
    creation_kind: DefaultWhenMissing[Literal["authored", "pack_copy", "member_copy"]] = "authored"


class LibraryArchiveManifest(BaseModel):
    """Full logical pack manifest, repeated unchanged under each domain root.

    Additional metadata is retained, including fields introduced by later
    domain steps. Body/domain validity and owner/formula checks belong to 4d.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    pack_uid: StrictOnWire[str]
    system_name: StrictOnWire[str]
    pack_name: StrictOnWire[str]
    display_name: StrictOnWire[str]
    version: DefaultWhenMissing[str] = "1.0"
    dependencies: DefaultWhenMissing[list[str]] = Field(default_factory=list)
    members: StrictOnWire[list[LibraryArchiveMember]]
    source_pack_uid: DefaultWhenMissing[str | None] = None
    defaults: DefaultWhenMissing[dict[str, str]] = Field(default_factory=dict)


@dataclass(frozen=True)
class LibraryArchivePack:
    manifest: LibraryArchiveManifest
    bodies: Mapping[str, dict[str, Any]]
