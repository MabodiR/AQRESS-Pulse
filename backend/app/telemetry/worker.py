import logging
import queue
import signal
import threading

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.mqtt.topics import TELEMETRY_SUBSCRIPTION
from app.telemetry.processor import InvalidTelemetryMessage, process_telemetry_message

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    messages: queue.Queue[tuple[str, bytes]] = queue.Queue()
    stopped = threading.Event()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="aqress-pulse-telemetry-worker",
    )
    client.username_pw_set(
        settings.mqtt_platform_username, settings.mqtt_platform_password
    )

    def on_connect(
        active_client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            logger.error(
                "MQTT telemetry worker connection rejected",
                extra={"reason": str(reason_code)},
            )
            return
        active_client.subscribe(TELEMETRY_SUBSCRIPTION, qos=1)
        logger.info("MQTT telemetry worker connected")

    def on_message(
        _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage
    ) -> None:
        messages.put((message.topic, message.payload))

    client.on_connect = on_connect
    client.on_message = on_message
    signal.signal(signal.SIGTERM, lambda *_args: stopped.set())
    signal.signal(signal.SIGINT, lambda *_args: stopped.set())
    client.connect(
        settings.mqtt_host,
        settings.mqtt_port,
        settings.mqtt_keepalive_seconds,
    )
    client.loop_start()
    try:
        while not stopped.is_set():
            try:
                topic, payload = messages.get(timeout=1)
            except queue.Empty:
                continue
            with Session(engine) as session:
                try:
                    process_telemetry_message(session, topic, payload)
                except InvalidTelemetryMessage as exc:
                    session.rollback()
                    logger.warning(
                        "Invalid MQTT telemetry payload",
                        extra={"topic": topic, "reason": str(exc)},
                    )
                except Exception:
                    session.rollback()
                    logger.exception("Unexpected telemetry processing failure")
    finally:
        client.disconnect()
        client.loop_stop()
        engine.dispose()


if __name__ == "__main__":
    main()
