"""Complete resolution inputs, independent of requested output bake tiles."""

from typing import Self

from pydantic import Field, model_validator

from app.dataModel.annotationPolicy import StrictEnumOnWire, StrictOnWire
from app.dataModel.placement.common import PlacementModel, PlacementPhase, PlacementUid
from app.dataModel.placement.prepared import PreparedPlacement
from app.dataModel.placement.result import ResolvedPlacement
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.planning.identity.planKey import OutputFingerprint
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.result import ResolvedPlacementV2


class PlacementBatch(PlacementModel):
    model_config = {**PlacementModel.model_config, "ser_json_bytes": "hex", "val_json_bytes": "hex"}

    world_uid: StrictOnWire[PlacementUid]
    snapshot_uid: StrictOnWire[PlacementUid]
    snapshot_revision: StrictOnWire[OutputFingerprint] = Field(strict=True, min_length=32, max_length=32)
    phase: StrictEnumOnWire[PlacementPhase]
    topology: StrictOnWire[WorldTopology]
    objects: StrictOnWire[tuple[PreparedPlacement, ...]]
    accepted: StrictOnWire[tuple[ResolvedPlacement, ...]]

    @model_validator(mode="after")
    def consistent_snapshot(self) -> Self:
        if self.phase == PlacementPhase.PRE_RELIEF and self.accepted:
            raise ValueError("pre_relief requires one joint input, without partial accepted winners")
        prepared = (*self.objects, *(result.prepared for result in self.accepted))
        identities = [obj.intent.identity for obj in prepared]
        if any(identity.world_uid != self.world_uid for identity in identities):
            raise ValueError("placement inputs must belong to batch world")
        uids = [identity.region_uid for identity in identities]
        if len(uids) != len(set(uids)):
            raise ValueError("duplicate region_uid across objects and accepted placements")
        for obj in self.objects:
            if obj.coastline is not None:
                if self.phase != PlacementPhase.PRE_RELIEF:
                    raise ValueError("coastline must be prepared on the pre_relief snapshot")
                if obj.coastline.snapshot_uid != self.snapshot_uid:
                    raise ValueError("coastline fact must identify the pre-carve batch snapshot")
        return self


class PlacementBatchV2(PlacementModel):
    model_config = PlacementBatch.model_config
    world_uid: PlacementUid
    snapshot_uid: PlacementUid
    snapshot_revision: OutputFingerprint = Field(strict=True, min_length=32, max_length=32)
    phase: PlacementPhase
    topology: WorldTopology
    objects: tuple[PlacementAdmissionInput, ...]
    accepted: tuple[ResolvedPlacementV2, ...]

    @model_validator(mode="after")
    def consistent_snapshot(self) -> Self:
        if self.phase is PlacementPhase.PRE_RELIEF and self.accepted:
            raise ValueError("pre_relief requires one joint input")
        identities = [o.header.identity for o in self.objects] + [o.identity for o in self.accepted]
        if any(i.world_uid != self.world_uid for i in identities):
            raise ValueError("placement inputs must belong to batch world")
        if len({i.region_uid for i in identities}) != len(identities):
            raise ValueError("duplicate region_uid across objects and accepted placements")
        return self
