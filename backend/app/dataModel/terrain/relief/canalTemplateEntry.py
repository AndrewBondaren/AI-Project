"""One ``worlds.canal_template_registry[]`` row — tz_terrain_relief R36q.

Entry XOR: ``earthen_canal: true`` XOR ``structure`` (R28).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.terrain.relief.canal import EarthenCanal, StructureCanal


class CanalStructureSpec(BaseModel):
    """Built/lined canal materials — refs → ``barrier_template_registry``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)


class CanalTemplateEntry(BaseModel):
    """Reusable canal description on the world (not inlined on every grade case)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[str]
    earthen_canal: DefaultOnWire[bool | None] = None
    structure: DefaultOnWire[CanalStructureSpec | None] = None

    @model_validator(mode="after")
    def _xor_earthen_or_structure(self) -> CanalTemplateEntry:
        has_earthen = self.earthen_canal is True
        has_structure = self.structure is not None
        if has_earthen and has_structure:
            raise ValueError(
                "canal entry earthen_canal XOR structure — both set (R28/R36q)"
            )
        if not has_earthen and not has_structure:
            raise ValueError(
                "canal entry needs earthen_canal: true or structure (R28/R36q)"
            )
        return self

    def to_canal(self) -> EarthenCanal | StructureCanal:
        """Typed runtime canal from this entry."""
        if self.earthen_canal is True:
            return EarthenCanal(system_type=self.system_type)
        assert self.structure is not None
        return StructureCanal(
            system_type=self.system_type,
            structure_refs=list(self.structure.structure_refs),
        )
