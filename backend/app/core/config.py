import os


class Settings:
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://192.168.1.19:1234/v1")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", None)


settings = Settings()