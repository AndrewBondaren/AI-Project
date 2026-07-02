from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.configManager import ConfigManager
from app.core.container import Container
from app.core.loggingConfig import setup_logging
from app.core.logMiddleware import RequestLoggingMiddleware
from app.core.logLevel import to_logging_level
from app.db.database import Database


def make_lifespan(db: Database):
    from app.db.models.gameSession import GameSession
    from app.db.models.message import Turn, Message, NodeExecutionLog
    from app.db.models.npc import Npc
    from app.db.models.player import Player
    from app.db.models.world import World
    from app.db.models.race import Race
    from app.db.models.world_perk import WorldPerk
    from app.db.models.namedLocation import NamedLocation
    from app.db.models.mapCell import MapCell
    from app.db.models.connectionNode import ConnectionNode
    from app.db.models.connectionEdge import ConnectionEdge
    from app.db.models.connectionEdgeCell import ConnectionEdgeCell
    from app.db.models.state import State
    from app.db.models.sessionPending import SessionPending
    from app.db.repositories.sqlite.pendingRepository import SqlitePendingRepository

    _models = [
        World, GameSession, Player, Npc, Turn, Message, NodeExecutionLog,
        Race, WorldPerk, NamedLocation, MapCell,
        ConnectionNode, ConnectionEdge, ConnectionEdgeCell,
        State, SessionPending,
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.connect()
        await db.apply_migrations()
        await db.validate_schema(_models)
        from app.dataModel.climate.worldClimateScalars import validate_world_row_climate_columns
        validate_world_row_climate_columns(World)
        await SqlitePendingRepository(db).cleanup_stale()
        yield
        await db.disconnect()
    return lifespan


def create_app():
    from app.core.appSettings import app_settings

    config_manager = ConfigManager()
    loaded = config_manager.load()
    if loaded:
        app_settings.update(**loaded)

    setup_logging(
        level=to_logging_level(app_settings.log_level),
        logger_levels=app_settings.logger_levels,
    )

    db = Database(path=app_settings.db_path)

    app = FastAPI(lifespan=make_lifespan(db))
    container = Container(config_manager=config_manager, db=db)
    app.state.container = container

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.routes.chat import router as chat_router
    from app.api.routes.settings import router as settings_router
    from app.api.routes.worlds import router as worlds_router
    from app.api.routes.races import router as races_router
    from app.api.routes.perks import router as perks_router
    from app.api.routes.locations import router as locations_router
    from app.api.routes.seed import router as seed_router
    from app.api.routes.characters import router as characters_router
    from app.api.routes.sessions import router as sessions_router
    from app.api.routes.map import router as map_router
    from app.api.routes.connections import router as connections_router
    from app.api.routes.debug import router as debug_router

    app.include_router(chat_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(worlds_router, prefix="/api")
    app.include_router(races_router, prefix="/api")
    app.include_router(perks_router, prefix="/api")
    app.include_router(locations_router, prefix="/api")
    app.include_router(seed_router, prefix="/api")
    app.include_router(characters_router, prefix="/api")
    app.include_router(sessions_router, prefix="/api")
    app.include_router(map_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(debug_router, prefix="/api")

    return app


app = create_app()
