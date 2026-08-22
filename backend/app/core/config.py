import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AQRESS Pulse API"
    app_version: str = "0.1.1"
    app_env: str = os.getenv("APP_ENV", "local")
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://aqress_pulse:aqress-pulse-local-only@localhost:5433/aqress_pulse",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "local-only-change-this-secret")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    admin_email: str | None = os.getenv("AQRESS_PULSE_ADMIN_EMAIL")
    admin_password: str | None = os.getenv("AQRESS_PULSE_ADMIN_PASSWORD")
    admin_first_name: str = os.getenv("AQRESS_PULSE_ADMIN_FIRST_NAME", "Local")
    admin_last_name: str = os.getenv("AQRESS_PULSE_ADMIN_LAST_NAME", "Administrator")
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_platform_username: str = os.getenv("MQTT_PLATFORM_USERNAME", "platform:control")
    mqtt_platform_password: str = os.getenv("MQTT_PLATFORM_PASSWORD", "local-platform-control-change-me")
    mqtt_keepalive_seconds: int = int(os.getenv("MQTT_KEEPALIVE_SECONDS", "30"))
    device_offline_timeout_seconds: int = int(os.getenv("DEVICE_OFFLINE_TIMEOUT_SECONDS", "90"))
    device_offline_check_interval_seconds: int = int(os.getenv("DEVICE_OFFLINE_CHECK_INTERVAL_SECONDS", "10"))

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
