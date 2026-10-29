"""Terrain-owned pre-coating evidence and computed decisions (GEO-1 §6.29-H)."""
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.planning.identity.planKey import InputFingerprint
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyDecision import ValueSelectionDecision
from app.dataModel.policy.policyFacts import FactValue, KnownFact
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


class SurfaceAspect(StrEnum):
    HORIZONTAL = "horizontal"
    RELIEF_FACE = "relief_face"


class SurfaceCoatingAction(StrEnum):
    APPLY_SHORE_SURFACE = "apply_shore_surface"
    KEEP_EXISTING_SURFACE = "keep_existing_surface"


class SurfaceCoatingReason(StrEnum):
    ROCK_CLIFF = "rock_cliff"
    SUPPORTED = "supported"


class SurfaceCoatingIssueCode(StrEnum):
    UNKNOWN_SUPPORT = "surface_coating_unknown_support"


class _CoatingRecord(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")


class SurfaceCoatingFacts(_CoatingRecord, frozen=True):
    world_uid: EntityUid
    support_input_fingerprint: InputFingerprint
    cell: FineXY
    face: Facing | None
    aspect: FactValue[SurfaceAspect]
    side_kind: FactValue[ReliefSideKind]
    material: FactValue[MaterialKey]
    substrate: FactValue[MaterialSubstrateKind]
    geometry_ref: PlanRef
    material_source_path: tuple[str | int, ...]

    @model_validator(mode="after")
    def coherent_evidence(self) -> Self:
        if len(self.support_input_fingerprint) != 32:
            raise ValueError("support fingerprint requires 32 bytes")
        if self.geometry_ref.key.world_uid != self.world_uid:
            raise ValueError("geometry evidence belongs to another world")
        if isinstance(self.aspect, KnownFact):
            if (self.aspect.value is SurfaceAspect.RELIEF_FACE) != (self.face is not None):
                raise ValueError("relief face requires explicit facing; horizontal has none")
        return self


class ShoreCoatingTarget(_CoatingRecord, frozen=True):
    terrain: TerrainKey
    material: MaterialKey


class SurfaceSupportPlan(_CoatingRecord, frozen=True):
    facts: tuple[SurfaceCoatingFacts, ...]

    @model_validator(mode="after")
    def unique_cells(self) -> Self:
        _require_order(tuple((f.cell, f.face) for f in self.facts))
        identities = {(f.world_uid, f.support_input_fingerprint) for f in self.facts}
        if len(identities) > 1:
            raise ValueError("support facts require one captured input")
        return self


class CoatingCellPlan(_CoatingRecord, frozen=True):
    cell: FineXY
    face: Facing | None
    decision: ValueSelectionDecision[SurfaceCoatingAction, SurfaceCoatingReason]
    target: ShoreCoatingTarget | None

    @model_validator(mode="after")
    def applicable_target(self) -> Self:
        applies = self.decision.behavior is SurfaceCoatingAction.APPLY_SHORE_SURFACE
        if applies != (self.target is not None):
            raise ValueError("only APPLY requires a resolved terrain/material pair")
        return self


class CoatingPlan(_CoatingRecord, frozen=True):
    cells: tuple[CoatingCellPlan, ...]

    @model_validator(mode="after")
    def unique_cells(self) -> Self:
        _require_order(tuple((c.cell, c.face) for c in self.cells))
        return self


def _require_order(identities: tuple[tuple[FineXY, Facing | None], ...]) -> None:
    if len(set(identities)) != len(identities) or identities != tuple(sorted(
            identities, key=lambda p: (p[0][1], p[0][0], p[1].value if p[1] else ""))):
        raise ValueError("coating cells/faces must be unique in canonical order")
