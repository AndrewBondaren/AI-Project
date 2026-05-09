# core/config.py

import os


class Settings:
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:8000/v1")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", None)


settings = Settings()