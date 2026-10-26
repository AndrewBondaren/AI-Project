"""Typed archive envelope — ``tz_template_library_packs.md`` §4.2.

The manifest describes transport and source identity only. Domain settings,
pack membership and provenance live in their own payloads. ZIP inventory and
source/payload identity checks belong to the archive codec, not this POJO.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.worldBundle.bundleSections import BundleSection, SECTION_PATHS

type ManifestText = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]


class BundleKind(StrEnum):
    """Archive/source kinds; wire strings are defined here once."""

    WORLD = "world"
    LIBRARY_PACK = "library_pack"


class _BundleSource(BaseModel):
    """Metadata supplied once by the exporter; no implicit current time."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    exporter: StrictOnWire[ManifestText]
    exported_at: StrictOnWire[AwareDatetime]
    content_hash: DefaultWhenMissing[ManifestText | None] = None

    @field_validator("exported_at", mode="before")
    @classmethod
    def _timestamp_wire(cls, value: object) -> object:
        if not isinstance(value, (str, datetime)):
            raise ValueError("exported_at must be an ISO 8601 UTC timestamp")
        return value

    @field_validator("exported_at")
    @classmethod
    def _utc_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("exported_at must use UTC")
        return value


class BundleWorldSource(_BundleSource):
    """World owner before import remapping; name is a source label."""

    kind: StrictOnWire[Literal[BundleKind.WORLD]]
    world_uid: StrictOnWire[ManifestText]
    world_name: StrictOnWire[ManifestText]


class BundleLibraryPackSource(_BundleSource):
    """One logical engine pack, possibly spanning several domain roots."""

    kind: StrictOnWire[Literal[BundleKind.LIBRARY_PACK]]
    pack_uid: StrictOnWire[ManifestText]


type BundleSource = Annotated[
    BundleWorldSource | BundleLibraryPackSource,
    Field(discriminator="kind"),
]


class BundleManifest(BaseModel):
    """Version 1 ``bundle.manifest.json`` shared by world and pack archives."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    SCHEMA_ID: ClassVar[str] = "SCH-BUNDLE-MANIFEST"

    kind: StrictOnWire[BundleKind]
    format_version: StrictOnWire[Literal[1]]
    source: StrictOnWire[BundleSource]
    sections: StrictOnWire[dict[str, str]]

    @field_validator("format_version", mode="before")
    @classmethod
    def _integer_version(cls, value: object) -> object:
        # Literal[1] alone also accepts True/1.0 in Pydantic.
        if type(value) is not int:
            raise ValueError("format_version must be an integer")
        return value

    @field_validator("sections")
    @classmethod
    def _section_paths(cls, value: dict[str, str]) -> dict[str, str]:
        for key, path in value.items():
            if key not in SECTION_PATHS or SECTION_PATHS[key] != path:
                raise ValueError(f"unknown section/path pair: {key!r} -> {path!r}")
        return value

    @model_validator(mode="after")
    def _archive_kind(self) -> Self:
        if self.source.kind != self.kind:
            raise ValueError("source.kind must match archive kind")
        if self.kind == BundleKind.WORLD and BundleSection.WORLD not in self.sections:
            raise ValueError("world archive must index the world section")
        if self.kind == BundleKind.LIBRARY_PACK and self.sections:
            raise ValueError("library_pack archive must have an empty sections index")
        return self
