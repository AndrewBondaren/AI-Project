import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).parent.parent.parent
_PROJECT_DIR = _BACKEND_DIR.parent


class DefaultConfig:
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://192.168.1.19:1234/v1")
    QWEN_API_KEY  = os.getenv("QWEN_API_KEY",  "sk-local")

    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://192.168.1.19:1234/v1")
    OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY",  "sk-local")

    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "http://192.168.1.19:1234/v1")
    ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY",  "sk-local")

    LLM_STREAMING: bool = os.getenv("LLM_STREAMING", "true").lower() != "false"

    DB_PATH: str = os.getenv("DB_PATH", "../db/game.db")

    # Уровни логирования для шумных сторонних логгеров
    LOGGER_LEVELS: dict = {"aiosqlite": "WARNING"}
