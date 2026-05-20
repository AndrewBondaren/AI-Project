from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.container import Container
from app.core.logging_config import setup_logging
from app.core.log_middleware import RequestLoggingMiddleware

import logging

setup_logging()


def create_app():
    app = FastAPI()
    container = Container()
    app.state.container = container

    # wire settings → container so update() can invalidate clients
    from app.core.appSettings import app_settings
    app_settings._container = container

    setup_logging()
    logging.getLogger("app.application.llm.clients.qwenClient").setLevel(logging.DEBUG)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # позже сузишь под домен фронта
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 🔥 импорт роутеров ПОСЛЕ создания app (важно для DI и циклов)

    from app.api.routes.chat import router as chat_router
    from app.api.routes.settings import router as settings_router
    #from app.api.routes.sessions import router as sessions_router
    #from app.api.routes.characters import router as characters_router

    app.include_router(chat_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    #app.include_router(sessions_router, prefix="/api")
    #app.include_router(characters_router, prefix="/api")

    return app


app = create_app()