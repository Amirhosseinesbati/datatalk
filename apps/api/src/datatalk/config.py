from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./datatalk.db"
    analytics_database_url: str | None = None
    datatalk_mode: str = "demo"
    datatalk_secret_key: str = "local-demo-change-me"
    datatalk_cookie_secure: bool = False
    datatalk_model_id: str = "gpt-4.1-mini"
    datatalk_demo_password: str = "DemoPass123!"
    datatalk_session_days: int = 7
    datatalk_statement_timeout_ms: int = 4000
    datatalk_row_cap: int = 200
    datatalk_import_max_bytes: int = 2_000_000
    datatalk_import_preview_ttl_hours: int = Field(default=24, ge=1, le=720)
    datatalk_model_input_usd_per_million: float | None = Field(default=None, ge=0)
    datatalk_model_output_usd_per_million: float | None = Field(default=None, ge=0)
    datatalk_analytics_role_password: str | None = None
    datatalk_app_role: str = "datatalk_app"
    datatalk_reader_role: str = "datatalk_reader"
    datatalk_allowed_origins: str = ""

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
