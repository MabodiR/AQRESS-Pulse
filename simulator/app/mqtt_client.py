import json
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt

from app.config_manager import apply_sensor_configuration
from app.device_state import DeviceState
from app.settings import SimulatorSettings
from app.telemetry import collect_due_readings

logger = logging.getLogger(__name__)
NAMESPACE = "aqress/pulse/v1/devices"


class SimulatorMqttClient:
    def __init__(self, settings: SimulatorSettings, state: DeviceState) -> None:
        self.settings = settings
        self.state = state
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"simulator-{settings.device_uid}")
        self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.random_source = random.Random(settings.random_seed)

    def run(self) -> None:
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, 30)
        self.client.loop_start()
        last_heartbeat = float("-inf")
        try:
            while True:
                now = time.monotonic()
                if now - last_heartbeat >= self.settings.heartbeat_interval_seconds:
                    self.publish_heartbeat()
                    last_heartbeat = now
                self.publish_telemetry(now_monotonic=now)
                time.sleep(self.settings.telemetry_poll_interval_seconds)
        finally:
            self.client.disconnect()
            self.client.loop_stop()

    def publish_heartbeat(self) -> None:
        payload = {
            "device_uid": self.settings.device_uid,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "status": "ONLINE",
            "uptime_seconds": int(time.monotonic() - self.state.started_monotonic),
            "firmware_version": self.settings.firmware_version,
            "wifi_rssi": -61,
            "free_memory": 183240,
        }
        self.client.publish(f"{NAMESPACE}/{self.settings.device_uid}/status", json.dumps(payload), qos=1)

    def publish_telemetry(self, *, now_monotonic: float | None = None) -> None:
        now = datetime.now(UTC)
        readings = collect_due_readings(
            self.state,
            self.random_source,
            now_monotonic=now_monotonic if now_monotonic is not None else time.monotonic(),
            recorded_at=now,
        )
        if not readings:
            return
        payload = {
            "message_id": str(uuid.uuid4()),
            "device_uid": self.settings.device_uid,
            "sent_at": now.isoformat().replace("+00:00", "Z"),
            "readings": readings,
        }
        self.client.publish(
            f"{NAMESPACE}/{self.settings.device_uid}/telemetry",
            json.dumps(payload),
            qos=1,
            retain=False,
        )
        logger.debug(
            "Telemetry batch published",
            extra={
                "device_uid": self.settings.device_uid,
                "message_id": payload["message_id"],
                "reading_count": len(readings),
            },
        )

    def _on_connect(self, client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        if reason_code.is_failure:
            logger.error("Simulator MQTT connection rejected", extra={"reason": str(reason_code)})
            return
        client.subscribe(f"{NAMESPACE}/{self.settings.device_uid}/config", qos=1)
        logger.info("Simulator connected", extra={"device_uid": self.settings.device_uid})

    def _on_message(self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            snapshot = json.loads(message.payload.decode("utf-8"))
            if not isinstance(snapshot, dict) or snapshot.get("device_uid") != self.settings.device_uid:
                raise ValueError("Configuration Device UID mismatch")
            results = [self._apply(sensor) for sensor in snapshot.get("sensors", [])]
            acknowledgement = {
                "message_id": snapshot.get("message_id", str(uuid.uuid4())),
                "device_uid": self.settings.device_uid,
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "results": results,
            }
            self.client.publish(f"{NAMESPACE}/{self.settings.device_uid}/config/ack", json.dumps(acknowledgement), qos=1)
            logger.info("Configuration acknowledgement published", extra={"device_uid": self.settings.device_uid, "message_id": acknowledgement["message_id"]})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Invalid configuration snapshot ignored", extra={"reason": str(exc)})

    def _apply(self, sensor: dict[str, Any]) -> dict[str, Any]:
        error = apply_sensor_configuration(sensor, self.state, force_failure=self.settings.force_config_failure)
        return {
            "sensor_uid": sensor.get("sensor_uid"),
            "configuration_version": sensor.get("configuration_version"),
            "status": "FAILED" if error else "APPLIED",
            "error": error,
        }
