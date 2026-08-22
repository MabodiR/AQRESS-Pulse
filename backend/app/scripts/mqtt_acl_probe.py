import argparse
import json
import threading
import time
import uuid

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.mqtt.topics import (
    config_ack_topic,
    config_topic,
    status_topic,
    telemetry_topic,
)


def connection_allowed(username: str | None, password: str | None) -> bool:
    finished = threading.Event()
    allowed = False
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-connect-{uuid.uuid4()}")
    if username is not None:
        client.username_pw_set(username, password)

    def on_connect(_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        nonlocal allowed
        allowed = not reason_code.is_failure
        finished.set()

    client.on_connect = on_connect
    client.connect(settings.mqtt_host, settings.mqtt_port, 10)
    client.loop_start()
    finished.wait(4)
    client.disconnect()
    client.loop_stop()
    return allowed


def publish_allowed(username: str, password: str, topic: str) -> bool:
    connected = threading.Event()
    published = threading.Event()
    disconnected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-publish-{uuid.uuid4()}")
    client.username_pw_set(username, password)
    client.on_connect = lambda *_args: connected.set()
    client.on_publish = lambda *_args: published.set()
    client.on_disconnect = lambda *_args: disconnected.set()
    client.connect(settings.mqtt_host, settings.mqtt_port, 10)
    client.loop_start()
    connected.wait(4)
    client.publish(topic, json.dumps({"probe": True}), qos=1)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and not published.is_set() and not disconnected.is_set():
        time.sleep(0.05)
    allowed = published.is_set() and not disconnected.is_set()
    client.disconnect()
    client.loop_stop()
    return allowed


def subscribe_allowed(username: str, password: str, topic: str) -> bool:
    finished = threading.Event()
    allowed = False
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-subscribe-{uuid.uuid4()}")
    client.username_pw_set(username, password)

    def on_connect(active_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
        if not reason_code.is_failure:
            active_client.subscribe(topic, qos=1)

    def on_subscribe(_client: mqtt.Client, _userdata: object, _mid: int, reason_codes: list[mqtt.ReasonCode], _properties: mqtt.Properties | None) -> None:
        nonlocal allowed
        allowed = bool(reason_codes) and not reason_codes[0].is_failure
        finished.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = lambda *_args: finished.set()
    client.connect(settings.mqtt_host, settings.mqtt_port, 10)
    client.loop_start()
    finished.wait(4)
    client.disconnect()
    client.loop_stop()
    return allowed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--device-uid", required=True)
    parser.add_argument("--other-device-uid", default="OTHER-DEVICE")
    parser.add_argument("--expect-rejected", action="store_true")
    args = parser.parse_args()
    if args.expect_rejected:
        assert not connection_allowed(args.username, args.password), "Credential unexpectedly connected"
        print("Rejected credential: PASS")
        return
    assert connection_allowed(args.username, args.password), "Valid credential was rejected"
    assert not connection_allowed(args.username, f"invalid-{uuid.uuid4()}"), "Invalid password connected"
    assert not connection_allowed(None, None), "Anonymous client connected"
    assert publish_allowed(args.username, args.password, status_topic(args.device_uid)), "Own status publish denied"
    assert publish_allowed(args.username, args.password, config_ack_topic(args.device_uid)), "Own ACK publish denied"
    assert publish_allowed(args.username, args.password, telemetry_topic(args.device_uid)), "Own telemetry publish denied"
    assert subscribe_allowed(args.username, args.password, config_topic(args.device_uid)), "Own config subscribe denied"
    assert not publish_allowed(args.username, args.password, status_topic(args.other_device_uid)), "Cross-Device publish allowed"
    assert not publish_allowed(args.username, args.password, telemetry_topic(args.other_device_uid)), "Cross-Device telemetry publish allowed"
    assert not subscribe_allowed(args.username, args.password, config_topic(args.other_device_uid)), "Cross-Device subscribe allowed"
    print("Authentication and per-Device broker ACLs: PASS")


if __name__ == "__main__":
    main()
