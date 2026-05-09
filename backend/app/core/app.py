from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app():
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # позже сузишь под домен фронта
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 🔥 импорт роутеров ПОСЛЕ создания app (важно для DI и циклов)

    from api.routes.chat import router as chat_router
    from api.routes.sessions import router as sessions_router
    from api.routes.characters import router as characters_router

    app.include_router(chat_router, prefix="/api")
    app.include_router(sessions_router, prefix="/api")
    app.include_router(characters_router, prefix="/api")

    return app


app = create_app()