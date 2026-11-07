"""Stable surface TLV registrations for app.dataModel.terrainMasks."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverClaimNoise, LandcoverTerrainPolicy
from app.dataModel.terrainMasks.mountain.enums import MountainKind, MountainRangeStyle
from app.dataModel.terrainMasks.mountain.specs import (
    MountainFormBySides,
    MountainRangeSides,
    MountainRangeSpec,
    MountainSaddleSpec,
    MountainSpec,
    PeakForm,
    PlateauForm,
    StarForm,
)
from app.dataModel.terrainMasks.regions.specs import FarmlandSpec, ForestSpec, PlainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy, RavinesCategoryPolicy


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (57, MountainsCategoryPolicy, CanonicalTypeKind.RECORD),
    (58, MountainKind, CanonicalTypeKind.ENUM),
    (59, MountainFormBySides, CanonicalTypeKind.RECORD),
    (60, StarForm, CanonicalTypeKind.RECORD),
    (61, PeakForm, CanonicalTypeKind.RECORD),
    (62, PlateauForm, CanonicalTypeKind.RECORD),
    (65, MountainRangeStyle, CanonicalTypeKind.ENUM),
    (66, RavinesCategoryPolicy, CanonicalTypeKind.RECORD),
    (67, MountainSpec, CanonicalTypeKind.RECORD),
    (71, MountainRangeSpec, CanonicalTypeKind.RECORD),
    (72, MountainRangeSides, CanonicalTypeKind.RECORD),
    (73, MountainSaddleSpec, CanonicalTypeKind.RECORD),
    (193, LandcoverClaimNoise, CanonicalTypeKind.RECORD),
    (194, LandcoverTerrainPolicy, CanonicalTypeKind.RECORD),
    (195, FarmlandSpec, CanonicalTypeKind.RECORD),
    (196, ForestSpec, CanonicalTypeKind.RECORD),
    (197, PlainSpec, CanonicalTypeKind.RECORD),
)
