from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///../data/local_route_agent.db"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

