"""Policy decision bound to a placement header before any footprint exists."""

from enum import Enum

from app.dataModel.placement.common import PlacementModel
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision


class PlacementAdmissionInput(PlacementModel):
    header: PlacementHeader
    decision: ObjectAdmissionDecision[Enum, Enum]
