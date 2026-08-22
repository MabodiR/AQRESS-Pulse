import logging
import queue
import signal
import threading
import time

import paho.mqtt.client as mqtt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.mqtt.control_plane import (
    InvalidControlMessage,
    mark_stale_devices_offline,
    process_control_message,
)
from app.mqtt.topics import CONTROL_SUBSCRIPTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    messages: queue.Queue[tuple[str, bytes]] = queue.Queue()
    stopped = threading.Event()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="aqress-pulse-control-worker")
    client.username_pw_set(settings.mqtt_platform_username, settings.mqtt_platform_password)

    def on_connect(active_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        if reason_code.is_failure:
            logger.error("MQTT control worker connection rejected", extra={"reason": str(reason_code)})
            return
        for topic in CONTROL_SUBSCRIPTIONS:
            active_client.subscribe(topic, qos=1)
        logger.info("MQTT control worker connected")

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        messages.put((message.topic, message.payload))

    client.on_connect = on_connect
    client.on_message = on_message
    signal.signal(signal.SIGTERM, lambda *_args: stopped.set())
    signal.signal(signal.SIGINT, lambda *_args: stopped.set())
    client.connect(settings.mqtt_host, settings.mqtt_port, settings.mqtt_keepalive_seconds)
    client.loop_start()
    last_offline_check = 0.0
    try:
        while not stopped.is_set():
            try:
                topic, payload = messages.get(timeout=1)
                with Session(engine) as session:
                    try:
                        process_control_message(session, topic, payload)
                    except InvalidControlMessage as exc:
                        session.rollback()
                        logger.warning("Invalid MQTT control payload", extra={"topic": topic, "reason": str(exc)})
            except queue.Empty:
                pass
            if time.monotonic() - last_offline_check >= settings.device_offline_check_interval_seconds:
                with Session(engine) as session:
                    mark_stale_devices_offline(session)
                last_offline_check = time.monotonic()
    finally:
        client.disconnect()
        client.loop_stop()
        engine.dispose()


if __name__ == "__main__":
    main()
