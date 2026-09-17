"""Environment-backed server configuration."""

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    gitlab_url: str = Field(validation_alias="GITLAB_URL")
    gitlab_token: SecretStr = Field(validation_alias="GITLAB_TOKEN")
    mcp_write_enabled: bool = Field(default=False, validation_alias="MCP_WRITE_ENABLED")
    gitlab_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias="GITLAB_TIMEOUT_SECONDS",
    )
    gitlab_max_pages: int = Field(
        default=100,
        ge=1,
        le=1000,
        validation_alias="GITLAB_MAX_PAGES",
    )
    gitlab_read_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias="GITLAB_READ_RETRIES",
    )
    gitlab_ca_bundle: Path | None = Field(default=None, validation_alias="GITLAB_CA_BUNDLE")

    @field_validator("gitlab_url")
    @classmethod
    def validate_gitlab_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"}:
            msg = "GITLAB_URL must use http or https"
            raise ValueError(msg)
        if not parsed.hostname or parsed.username or parsed.password:
            msg = "GITLAB_URL must contain a host and no user information"
            raise ValueError(msg)
        if parsed.query or parsed.fragment:
            msg = "GITLAB_URL must not contain a query or fragment"
            raise ValueError(msg)
        path = parsed.path.rstrip("/")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))

    @field_validator("gitlab_token")
    @classmethod
    def validate_gitlab_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            msg = "GITLAB_TOKEN must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("gitlab_ca_bundle", mode="before")
    @classmethod
    def empty_ca_bundle_is_none(cls, value: object) -> object:
        return None if value == "" else value
