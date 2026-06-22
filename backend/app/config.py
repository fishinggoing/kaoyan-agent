from pathlib import Path
from pydantic_settings import BaseSettings


def _find_env_file() -> str | None:
    """Find the first available .env file.

    Search order (first match wins):
      1. ~/.gradschool/.env   — secure, outside repo (production)
      2. <project_root>/.env  — legacy fallback (development)
    """
    candidates = [
        Path.home() / ".gradschool" / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


class Settings(BaseSettings):
    model_config = {
        "env_file": _find_env_file() or ".env",
        "env_file_encoding": "utf-8",
    }

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    database_url: str = "sqlite:///./gradschool.db"
    chroma_persist_dir: str = "./chroma_data"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS: comma-separated origins, e.g. "http://localhost:5173,http://192.168.1.100:8000"
    allow_origins: str = "http://localhost:5173"

    # Frontend static files dir (for production serving)
    static_dir: str = ""

    # API Key for protecting write/LLM endpoints (X-API-Key header)
    # If not set, protected endpoints are open — insecure, dev only!
    api_key: str = ""

    # Server酱 push notification key (https://sct.ftqq.com/)
    serverchan_key: str = ""


settings = Settings()
