from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.container import Container
from app.core.logging_config import setup_logging
from app.core.log_middleware import RequestLoggingMiddleware
from app.core.logLevel import to_logging_level


def create_app():
    from app.core.appSettings import app_settings

    setup_logging(level=to_logging_level(app_settings.log_level))

    app = FastAPI()
    container = Container()
    app.state.container = container

    app_settings._container = container

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
