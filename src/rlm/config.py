from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Конфигурация RLM"""
    buffer_meters: int = 500
    max_cloud_cover: int = 30
    default_start_date: str = "2024-04-01"
    default_end_date: str = "2024-09-30"
    copernicus_username: Optional[str] = None
    copernicus_password: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    litellm_model: str = "openrouter/qwen/qwen3-70b"

    class Config:
        env_file = ".env"
        env_prefix = "RLM_"
        extra = "ignore"


settings = Settings()
