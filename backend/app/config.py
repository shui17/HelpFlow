from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """读取应用配置，环境变量优先于 .env。"""

    model_config = SettingsConfigDict(
        env_prefix="HELPFLOW_",
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="HelpFlow", min_length=1)
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr = SecretStr("mysql+asyncmy://helpflow@127.0.0.1:3306/helpflow?charset=utf8mb4")
    jwt_secret_key: SecretStr | None = None
    jwt_access_token_expire_minutes: int = Field(default=120, ge=1, le=1440)

    auth_rate_limit_enabled: bool = True
    auth_rate_window_seconds: int = Field(default=60, ge=1, le=3600)
    auth_login_ip_limit: int = Field(default=60, ge=1, le=10000)
    auth_login_account_limit: int = Field(default=10, ge=1, le=1000)
    auth_register_ip_limit: int = Field(default=10, ge=1, le=1000)

    def signing_key(self) -> str:
        value = self.jwt_secret_key.get_secret_value() if self.jwt_secret_key else ""
        if len(value.encode("utf-8")) < 32 or value == "replace_with_a_long_random_value":
            raise ValueError("请配置至少 32 字节的 HELPFLOW_JWT_SECRET_KEY 随机密钥")
        return value
