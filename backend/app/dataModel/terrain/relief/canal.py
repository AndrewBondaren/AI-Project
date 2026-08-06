"""Resolved canal kinds — tz_terrain_relief R28 (XOR earthen | structure).

Wire knobs stay flat XOR; runtime SoT is this union.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class EarthenCanal(BaseModel):
    """Landform ditch — relief domain (not barrier materialize)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: Literal["earthen"] = "earthen"
    # Registry provenance when cut came from canal_template_registry / canal_ref
    system_type: DefaultOnWire[str | None] = None


class StructureCanal(BaseModel):
    """Lined/built canal — refs → barrier_template_registry (BAR-1 materialize)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: Literal["structure"] = "structure"
    system_type: StrictOnWire[str]
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)


Canal = Annotated[
    Union[EarthenCanal, StructureCanal],
    Field(discriminator="kind"),
]
