from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.sectionImportGate import gate_section_import
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.jsonValidation.types import SectionKey
from app.application.worldData.settlementPersistScope import (
    OUTDOOR_SCOPES,
    SettlementPersistScope,
)

router = APIRouter()

_SETTLEMENT_TYPES = frozenset({"city", "town", "village", "camp", "hamlet"})
_generator = SettlementGeneratorService()

_SCOPE_ALIASES: dict[str, frozenset[SettlementPersistScope]] = {
    "outdoor": OUTDOOR_SCOPES,
    "occupancy": frozenset({SettlementPersistScope.OCCUPANCY}),
}


def _resolve_scopes(scope: str) -> frozenset[SettlementPersistScope]:
    if scope in _SCOPE_ALIASES:
        return _SCOPE_ALIASES[scope]
    try:
        return frozenset({SettlementPersistScope(scope)})
    except ValueError as exc:
        valid = sorted({s.value for s in SettlementPersistScope} | set(_SCOPE_ALIASES))
        raise HTTPException(
            status_code=422,
            detail=f"Unknown scope '{scope}'. Valid: {valid}",
        ) from exc


@router.get("/worlds/{world_uid}/locations")
async def list_locations(world_uid: str, container=Depends(get_container)) -> list[dict]:
    locs = await container.location_service().get_all(world_uid)
    return [asdict(l) for l in locs]


@router.get("/worlds/{world_uid}/locations/{location_uid}")
async def get_location(
    world_uid: str,
    location_uid: str,
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().get_by_id(world_uid, location_uid)
    return asdict(loc)


@router.get("/worlds/{world_uid}/locations/{location_uid}/children")
async def get_children(
    world_uid: str,
    location_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    locs = await container.location_service().get_children(world_uid, location_uid)
    return [asdict(l) for l in locs]


@router.post("/worlds/{world_uid}/locations", status_code=201)
async def create_location(
    world_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().create(world_uid, data)
    return asdict(loc)


@router.put("/worlds/{world_uid}/locations/{location_uid}")
async def update_location(
    world_uid: str,
    location_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().update(world_uid, location_uid, data)
    return asdict(loc)


@router.delete("/worlds/{world_uid}/locations/{location_uid}", status_code=204)
async def delete_location(
    world_uid: str,
    location_uid: str,
    container=Depends(get_container),
) -> None:
    await container.location_service().delete(world_uid, location_uid)


@router.post("/worlds/{world_uid}/locations/import")
async def import_locations(
    world_uid: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="Locations JSON must be an array")

    await gate_section_import(
        container,
        world_uid=world_uid,
        section=SectionKey.LOCATIONS,
        payload=data,
    )

    result = await container.location_service().import_from_json(world_uid, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/worlds/{world_uid}/locations/{location_uid}/generate-settlement")
async def generate_settlement(
    world_uid: str,
    location_uid: str,
    scope: str = Query(default="outdoor"),
    skip_if_initialized: bool = Query(default=True),
    container=Depends(get_container),
) -> JSONResponse:
    """
    Debug only — production: engine DAG node via SettlementPersistService.

    Materializes settlement layout scopes (occupancy / outdoor / individual).
    """
    world = await container.world_service().get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    settlement = await container.location_service().get_by_id(world_uid, location_uid)
    if settlement.system_location_type not in _SETTLEMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Location '{location_uid}' is not a settlement type",
        )

    scopes = _resolve_scopes(scope)
    layout = None
    occupancy_cells = None

    needs_layout = bool(scopes & (OUTDOOR_SCOPES - {SettlementPersistScope.OCCUPANCY}))
    if SettlementPersistScope.OCCUPANCY in scopes:
        occupancy_cells = _generator.plan_occupancy_only(world, settlement)
    if needs_layout:
        existing = await container.map_cell_service().get_all(world_uid)
        terrain_cells = [
            c for c in existing
            if c.location_uid == location_uid
        ] or None
        layout = _generator.generate_layout(world, settlement, terrain_cells)

    result = await container.settlement_persist_service().persist(
        world,
        settlement,
        layout=layout,
        occupancy_cells=occupancy_cells,
        scopes=scopes,
        skip_if_initialized=skip_if_initialized,
    )

    payload = result.to_dict()
    if layout is not None:
        payload["dominant_material"] = layout.dominant_material

    return JSONResponse(content=payload)
