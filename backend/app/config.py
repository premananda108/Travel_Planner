from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./travel_planner.db"
    API_USERNAME: str = "admin"
    API_PASSWORD: str = "travelsecret"
    ART_API_BASE_URL: str = "https://api.artic.edu/api/v1"
    CACHE_TTL_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
