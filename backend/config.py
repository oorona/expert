import pathlib
import os


def read_secret(name: str, default: str = "") -> str:
    """Read a Docker secret from /run/secrets/ or fall back to env var."""
    base = pathlib.Path("/run/secrets")
    secret_path = (base / name).resolve()
    # Prevent path traversal
    if not str(secret_path).startswith(str(base)):
        raise ValueError(f"Invalid secret name: {name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return os.getenv(name.upper(), default)


class Settings:
    GEMINI_API_KEY: str = read_secret("gemini_api_key")
    DB_PASSWORD: str = read_secret("db_password", "postgres")
    DB_USER: str = os.getenv("POSTGRES_USER", "postgres")
    DB_NAME: str = os.getenv("POSTGRES_DB", "expert")
    DB_HOST: str = os.getenv("POSTGRES_HOST", "expert-db")
    DB_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))

    # Context caching settings
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour default


settings = Settings()
