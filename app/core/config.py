import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Automatically locate and load root .env or backend .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_ENV = BASE_DIR / ".env"
BACKEND_ENV = BASE_DIR / "backend" / ".env"
LOCAL_ENV = Path(".env")

for env_path in [ROOT_ENV, BACKEND_ENV, LOCAL_ENV]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)

def get_env_val(key: str, default: str = "") -> str:
    for env_path in [ROOT_ENV, BACKEND_ENV, LOCAL_ENV]:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
    return (os.getenv(key) or default).strip()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", str(ROOT_ENV), str(BACKEND_ENV)),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "CodeMind"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # AI & Memory Keys
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    HINDSIGHT_API_KEY: str = ""
    HINDSIGHT_BASE_URL: str = "https://api.hindsight.vectorize.io"
    HINDSIGHT_BANK_ID: str = "codemind"
    
    # OAuth Keys
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    
    # Security & DB
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.as_posix()}/data/codemind.db"
    SESSION_SECRET: str = "codemind_secret_session_key_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def github_client_id_clean(self) -> str:
        return get_env_val("GITHUB_CLIENT_ID", self.GITHUB_CLIENT_ID)

    @property
    def github_client_secret_clean(self) -> str:
        return get_env_val("GITHUB_CLIENT_SECRET", self.GITHUB_CLIENT_SECRET)

    @property
    def google_client_id_clean(self) -> str:
        return get_env_val("GOOGLE_CLIENT_ID", self.GOOGLE_CLIENT_ID)

    @property
    def google_client_secret_clean(self) -> str:
        return get_env_val("GOOGLE_CLIENT_SECRET", self.GOOGLE_CLIENT_SECRET)

settings = Settings()


