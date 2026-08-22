import threading

import paho.mqtt.client as mqtt

from app.core.config import settings


class MqttPublishError(RuntimeError):
    pass


class MqttPublisher:
    def publish(self, topic: str, payload: str, *, qos: int = 1, retain: bool = True) -> None:
        connected = threading.Event()
        connection_error: list[str] = []
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="aqress-pulse-api")
        client.username_pw_set(settings.mqtt_platform_username, settings.mqtt_platform_password)

        def on_connect(_client: mqtt.Client, _userdata: object, _flags: mqtt.ConnectFlags, reason_code: mqtt.ReasonCode, _properties: mqtt.Properties | None) -> None:
            if reason_code.is_failure:
                connection_error.append(str(reason_code))
            connected.set()

        client.on_connect = on_connect
        try:
            client.connect(settings.mqtt_host, settings.mqtt_port, settings.mqtt_keepalive_seconds)
            client.loop_start()
            if not connected.wait(timeout=5) or connection_error:
                raise MqttPublishError(f"MQTT connection failed: {connection_error[0] if connection_error else 'timeout'}")
            info = client.publish(topic, payload, qos=qos, retain=retain)
            info.wait_for_publish(timeout=5)
            if not info.is_published():
                raise MqttPublishError("MQTT broker did not confirm publication.")
        except (OSError, mqtt.MQTTException) as exc:
            raise MqttPublishError("MQTT publication failed.") from exc
        finally:
            client.disconnect()
            client.loop_stop()
