"""Compose domain-owned surface bindings in stable TLV ID order."""

from itertools import chain

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry
from app.application.worldData.planning.encoding import surfaceBindings as planningBindings
from app.dataModel.climate.encoding import surfaceBindings as climateBindings
from app.dataModel.economy.encoding import surfaceBindings as economyBindings
from app.dataModel.fields.encoding import surfaceBindings as fieldsBindings
from app.dataModel.hydrology.encoding import surfaceBindings as hydrologyBindings
from app.dataModel.locations.encoding import surfaceBindings as locationsBindings
from app.dataModel.materials.encoding import surfaceBindings as materialsBindings
from app.dataModel.placement.encoding import surfaceBindings as placementBindings
from app.dataModel.policy.encoding import surfaceBindings as policyBindings
from app.dataModel.regions.encoding import surfaceBindings as regionsBindings
from app.dataModel.spatial.encoding import surfaceBindings as spatialBindings
from app.dataModel.terrain.designedWater.encoding import surfaceBindings as designedWaterBindings
from app.dataModel.terrain.encoding import surfaceBindings as terrainBindings
from app.dataModel.terrain.relief.encoding import surfaceBindings as reliefBindings
from app.dataModel.terrainMasks.encoding import surfaceBindings as terrainMasksBindings
from app.dataModel.topology.encoding import surfaceBindings as topologyBindings
from app.dataModel.validation.encoding import surfaceBindings as validationBindings
from app.dataModel.worldPack.encoding import surfaceBindings as worldPackBindings


_bindings = chain(
    planningBindings.BINDINGS,
    climateBindings.BINDINGS,
    economyBindings.BINDINGS,
    fieldsBindings.BINDINGS,
    hydrologyBindings.BINDINGS,
    locationsBindings.BINDINGS,
    materialsBindings.BINDINGS,
    placementBindings.BINDINGS,
    policyBindings.BINDINGS,
    regionsBindings.BINDINGS,
    spatialBindings.BINDINGS,
    designedWaterBindings.BINDINGS,
    terrainBindings.BINDINGS,
    reliefBindings.BINDINGS,
    terrainMasksBindings.BINDINGS,
    topologyBindings.BINDINGS,
    validationBindings.BINDINGS,
    worldPackBindings.BINDINGS,
)
SURFACE_MANIFEST = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=type_id, python_type=owner, kind=kind)
    for type_id, owner, kind in sorted(_bindings, key=lambda entry: entry[0])
))
