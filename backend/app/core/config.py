import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AQRESS SenseGrid API"
    app_version: str = "0.1.1"
    app_env: str = os.getenv("APP_ENV", "local")
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()

