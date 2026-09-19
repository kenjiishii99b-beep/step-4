from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Apparel POS API"
    ENVIRONMENT: str = "local"

    DATABASE_URL: str = (
        "mysql+asyncmy://apparel_pos:apparel_pos_password@localhost:3306/apparel_pos"
    )
    # Azure Database for MySQL Flexible Server は既定で TLS 接続を要求する。
    # asyncmy は URL クエリの ssl=true を文字列のまま受け取り型エラーになるため、
    # 接続オプションとして明示的にブール値で渡す必要がある。
    DATABASE_SSL: bool = False

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 480

    LOGIN_MAX_FAILURES: int = 5
    LOGIN_MAX_FAILURES_PER_IP: int = 20
    LOGIN_LOCKOUT_MINUTES: int = 15

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
