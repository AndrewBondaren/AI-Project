"""Caller-owned typed rows and a membership-scoped full relief template."""
from app.application.templateLibrary.templateContracts import ReliefTemplateSnapshot, TemplateEntry
from app.application.worldData.planning.composition.support.surfaceSupportCapture import SurfaceSupportCapture
from app.application.encoding.canonicalCodec import digest
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy

UID="00000000-0000-0000-0000-000000000001"
PACK="00000000-0000-0000-0000-000000000002"


def template():
    return ReliefTemplate(system_name="rock-face",display_name="Rock face",context=ReliefContext.MOUNTAIN,
        side_recipe=MountainSideRecipe(default_side_kind=ReliefSideKind.SHEER))


def members(body=None):
    return ReliefTemplateSnapshot("world",{UID:TemplateEntry(UID,PACK,body if body is not None else template())})


def sources():
    return dict(seed=1,grid=SurfaceGridSettings(fine_span=2,light_side=2),
        topology=WorldTopology(mode="planar",bounds=WorldBounds(x_min=0,x_max=1,y_min=0,y_max=1)),
        terrain=WorldTerrainRegistry.canonical_defaults(),materials=WorldMaterialRegistry.canonical_defaults(),
        masks=WorldTerrainMasks(),region_states=(),relief_policy=WorldReliefPickPolicy(),
        templates=members(),refine_policy=ParentLightRefinePolicy())


def captured(**overrides):
    return SurfaceSupportCapture().capture("world",**(sources()|overrides))


def fingerprint(value):
    return digest(value,SURFACE_MANIFEST)
