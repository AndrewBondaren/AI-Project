"""Required world lookup shared by repository-backed application writers."""

from app.application.worldData.errors import WorldDataNotFoundError
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


async def require_world(repo: IWorldRepository, world_uid: str) -> World:
    world = await repo.get_by_id(world_uid)
    if world is None:
        raise WorldDataNotFoundError(f"World '{world_uid}' not found")
    return world
