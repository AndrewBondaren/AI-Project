import os


class Settings:
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://192.168.1.19:1234/v1")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-local")

    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://192.168.1.19:1234/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-local")

    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "http://192.168.1.19:1234/v1")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-local")


settings = Settings()