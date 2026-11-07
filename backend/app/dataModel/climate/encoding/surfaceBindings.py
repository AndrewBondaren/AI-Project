"""Stable surface TLV registrations for app.dataModel.climate."""

from app.dataModel.climate.climatePoleBlendDefaults import ClimatePoleBlendDefaults
from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan, ResolvedClimateProfile
from app.dataModel.climate.planning.climatePoints import AnchorSource, ClimateAnchorPoint, ClimatePolePoint
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput, ManualPoleInput
from app.dataModel.climate.planning.inputs.climateLocalInput import (
    ClimateFeaturePolicy,
    ClimateLocalInput,
    ProminenceScale,
)
from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (1, ClimateBaseInput, CanonicalTypeKind.RECORD),
    (3, ClimatePoleMode, CanonicalTypeKind.ENUM),
    (4, ClimatePolePreset, CanonicalTypeKind.ENUM),
    (5, WorldClimateZoneRegistry, CanonicalTypeKind.RECORD),
    (6, ClimateZoneEntry, CanonicalTypeKind.RECORD),
    (7, ManualPoleInput, CanonicalTypeKind.RECORD),
    (8, PoleKind, CanonicalTypeKind.ENUM),
    (9, ResolvedClimateProfile, CanonicalTypeKind.RECORD),
    (10, ClimateZoneProfileData, CanonicalTypeKind.RECORD),
    (11, ClimatePoleBlendDefaults, CanonicalTypeKind.RECORD),
    (12, ClimateLocalInput, CanonicalTypeKind.RECORD),
    (13, ClimateAnchorPoint, CanonicalTypeKind.RECORD),
    (14, AnchorSource, CanonicalTypeKind.ENUM),
    (15, ClimateFeaturePolicy, CanonicalTypeKind.RECORD),
    (24, ProminenceScale, CanonicalTypeKind.ENUM),
    (93, PlanEnvelope[ClimateBasePlan], CanonicalTypeKind.RECORD),
    (102, ClimateBasePlan, CanonicalTypeKind.RECORD),
    (103, ClimatePolePoint, CanonicalTypeKind.RECORD),
    (104, PoleSource, CanonicalTypeKind.ENUM),
    (112, PlanEnvelope[ClimateLocalPlan], CanonicalTypeKind.RECORD),
    (113, ClimateLocalPlan, CanonicalTypeKind.RECORD),
)
