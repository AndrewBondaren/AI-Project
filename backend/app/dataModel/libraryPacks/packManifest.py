"""Typed ``pack.manifest.json`` — tz_template_library_packs §4.

The manifest is pack metadata kept next to template bodies inside the pack
folder (``{domain_root}/{pack_name}/pack.manifest.json``); FS scanners never
interpret it as a template body. ``source_pack_uid`` of the pack and
``source_template_uid`` of members appear only in bundle manifests of remapped
packs — an FS-author manifest declares no provenance (§4).

``library_kind`` carries a ``LibraryKind`` value; the enum itself lives in
``app.ids`` — dataModel never imports the application
layer, so kind membership is validated at the consumer boundary (same rule as
``LibraryPinEntry``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire


class LibraryPackManifestMember(BaseModel):
    """One declared member: local key → pack-owned ``template_uid``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    library_kind: StrictOnWire[str]
    local_uid: StrictOnWire[str]
    template_uid: StrictOnWire[str]
    # Path of the body file relative to the domain root (FS import).
    source_file: StrictOnWire[str]
    source_template_uid: DefaultWhenMissing[str | None] = None


class LibraryPackManifest(BaseModel):
    """Pack identity + metadata + dependencies + declared members."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    pack_uid: StrictOnWire[str]
    system_name: StrictOnWire[str]
    pack_name: StrictOnWire[str]
    display_name: StrictOnWire[str]
    version: DefaultWhenMissing[str] = "1.0"
    dependencies: DefaultWhenMissing[list[str]] = Field(default_factory=list)
    members: StrictOnWire[list[LibraryPackManifestMember]]
    source_pack_uid: DefaultWhenMissing[str | None] = None
