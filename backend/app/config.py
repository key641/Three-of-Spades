from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///../data/local_route_agent.db"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "openai/gpt-5.4-mini"
    openai_base_url: str = "https://api.ofox.ai/v1"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    amap_web_service_key: str = ""
    map_route_provider: str = "mock"
    planning_pipeline_mode: str = ""
    planning_pipeline_rollout_percent: int = 100
    planning_pipeline_v2: bool | None = None
    planning_pipeline_shadow: bool | None = None
    route_model_enabled: bool = False
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env.example", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return init_settings, env_settings, dotenv_settings, file_secret_settings


settings = Settings()
