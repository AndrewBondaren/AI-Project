from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config_manager import ConfigManager
from app.core.container import Container
from app.core.logging_config import setup_logging
from app.core.log_middleware import RequestLoggingMiddleware
from app.core.logLevel import to_logging_level
from app.db.database import Database


def make_lifespan(db: Database):
    from app.db.models.gameSession import GameSession
    from app.db.models.message import Message
    from app.db.models.npc import Npc
    from app.db.models.player import Player
    from app.db.models.world import World

    _models = [World, GameSession, Player, Npc, Message]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.connect()
        await db.apply_migrations()
        await db.validate_schema(_models)
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

    app.include_router(chat_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")

    return app


app = create_app()
