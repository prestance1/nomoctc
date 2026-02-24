from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(env_file=".env")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "nomostc"
    mongo_max_pool_size: int = 50
    mongo_min_pool_size: int = 10


settings = Settings()
