from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(validation_alias="APP_NAME")
    app_env: str = Field(validation_alias="APP_ENV")
    database_url: str = Field(validation_alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
