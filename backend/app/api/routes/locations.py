from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    SettlementOutdoorExtractError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    SettlementOutdoorError,
    SettlementOutdoorNotFoundError,
    SettlementOutdoorPackMissingError,
)

router = APIRouter()


def _http_from_outdoor(exc: SettlementOutdoorError) -> HTTPException:
    if isinstance(exc, SettlementOutdoorNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


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


@router.get("/worlds/{world_uid}/locations/{location_uid}/render-grid")
async def render_location_grid(
    world_uid: str,
    location_uid: str,
    z: int | None = Query(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — ASCII grid for one location (pack: location_terrain; legacy: map_cells)."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    loc = await container.location_service().get_by_id(world_uid, location_uid)
    if loc is None:
        raise HTTPException(status_code=404, detail=f"Location '{location_uid}' not found")

    world = await container.world_service().get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    svc = MapGridRenderService(container.map_cell_service())
    payload = await svc.render_location_grid(world, location_uid, z=z)
    return JSONResponse(content=payload)


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

    result = await container.location_service().import_from_json(world_uid, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/worlds/{world_uid}/locations/{location_uid}/generate-settlement")
async def generate_settlement(
    world_uid: str,
    location_uid: str,
    skip_if_initialized: bool = Query(default=True),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — outdoor etalon via SettlementOutdoorOrchestrator (C11)."""
    try:
        result = await container.settlement_outdoor_orchestrator().materialize(
            world_uid,
            location_uid,
            skip_if_initialized=skip_if_initialized,
        )
    except (SettlementOutdoorError, SettlementOutdoorExtractError) as exc:
        raise _http_from_outdoor(
            exc if isinstance(exc, SettlementOutdoorError) else SettlementOutdoorError(str(exc))
        ) from exc
    return JSONResponse(content=result.to_dict())


@router.post("/worlds/{world_uid}/generate-settlements")
async def generate_settlements(
    world_uid: str,
    all_settlements: bool = Query(default=False, alias="all"),
    under: str | None = Query(default=None),
    state_uid: str | None = Query(default=None),
    skip_if_initialized: bool = Query(default=True),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug C16 selectors — same orchestrator as generate-settlement."""
    selected = sum(1 for flag in (all_settlements, bool(under), bool(state_uid)) if flag)
    if selected != 1:
        raise HTTPException(
            status_code=422,
            detail="Specify exactly one selector: all=1, under=<uid>, or state_uid=<uid>",
        )
    orch = container.settlement_outdoor_orchestrator()
    try:
        if all_settlements:
            batch = await orch.materialize_all(
                world_uid, skip_if_initialized=skip_if_initialized,
            )
        elif under:
            batch = await orch.materialize_under(
                world_uid, under, skip_if_initialized=skip_if_initialized,
            )
        else:
            batch = await orch.materialize_state(
                world_uid, state_uid or "", skip_if_initialized=skip_if_initialized,
            )
    except SettlementOutdoorError as exc:
        raise _http_from_outdoor(exc) from exc
    status_code = 200 if not batch.failed_uids else 207
    return JSONResponse(status_code=status_code, content=batch.to_dict())
