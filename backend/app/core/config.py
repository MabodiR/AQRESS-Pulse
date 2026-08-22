import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AQRESS SenseGrid API"
    app_version: str = "0.1.1"
    app_env: str = os.getenv("APP_ENV", "local")
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://sensegrid:sensegrid-local-only@localhost:5433/sensegrid",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "local-only-change-this-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    admin_email: str | None = os.getenv("SENSEGRID_ADMIN_EMAIL")
    admin_password: str | None = os.getenv("SENSEGRID_ADMIN_PASSWORD")
    admin_first_name: str = os.getenv("SENSEGRID_ADMIN_FIRST_NAME", "Local")
    admin_last_name: str = os.getenv("SENSEGRID_ADMIN_LAST_NAME", "Administrator")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
