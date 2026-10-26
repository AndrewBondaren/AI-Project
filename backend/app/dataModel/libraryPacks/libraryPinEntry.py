"""One ``worlds.library_pins[]`` pin — tz_template_library_packs §1.1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire


class LibraryPinEntry(BaseModel):
    """Author pin: pair ``(library_kind, template_uid)`` — remapped on pack copy.

    ``library_kind`` carries a ``LibraryKind`` value; the enum itself lives
    in ``app.ids`` — dataModel never imports the
    application layer, so membership is validated at the consumer boundary.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    library_kind: StrictOnWire[str]
    template_uid: StrictOnWire[str]
