import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatorSettings:
    device_uid: str = os.getenv("SIMULATOR_DEVICE_UID", "")
    mqtt_username: str = os.getenv("SIMULATOR_MQTT_USERNAME", "")
    mqtt_password: str = os.getenv("SIMULATOR_MQTT_PASSWORD", "")
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    heartbeat_interval_seconds: int = int(os.getenv("SIMULATOR_HEARTBEAT_INTERVAL_SECONDS", "15"))
    firmware_version: str = os.getenv("SIMULATOR_FIRMWARE_VERSION", "0.1.0")
    force_config_failure: bool = os.getenv("SIMULATOR_FORCE_CONFIG_FAILURE", "false").casefold() == "true"
    telemetry_poll_interval_seconds: float = float(
        os.getenv("SIMULATOR_TELEMETRY_POLL_INTERVAL_SECONDS", "0.25")
    )
    random_seed: int = int(os.getenv("SIMULATOR_RANDOM_SEED", "20260822"))

    def validate(self) -> None:
        missing = [name for name, value in (("SIMULATOR_DEVICE_UID", self.device_uid), ("SIMULATOR_MQTT_USERNAME", self.mqtt_username), ("SIMULATOR_MQTT_PASSWORD", self.mqtt_password)) if not value]
        if missing:
            raise RuntimeError(f"Missing required simulator environment variables: {', '.join(missing)}")
