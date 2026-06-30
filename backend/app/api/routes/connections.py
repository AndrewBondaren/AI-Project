"""Connection graph read API — debug harness for persist cycle smoke."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.api.deps import get_container

router = APIRouter()


@router.get("/worlds/{world_uid}/connections/nodes")
async def list_connection_nodes(
    world_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    nodes = await container.connection_node_repository().get_by_world(world_uid)
    return [asdict(n) for n in nodes]


@router.get("/worlds/{world_uid}/connections/edges")
async def list_connection_edges(
    world_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    edges = await container.connection_edge_repository().get_by_world(world_uid)
    return [asdict(e) for e in edges]


@router.get("/worlds/{world_uid}/connections")
async def list_connections(
    world_uid: str,
    container=Depends(get_container),
) -> dict:
    node_repo = container.connection_node_repository()
    edge_repo = container.connection_edge_repository()
    nodes = await node_repo.get_by_world(world_uid)
    edges = await edge_repo.get_by_world(world_uid)
    return {
        "nodes": [asdict(n) for n in nodes],
        "edges": [asdict(e) for e in edges],
    }
