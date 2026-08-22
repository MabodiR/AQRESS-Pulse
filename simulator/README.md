# AQRESS Pulse Device Simulator

The Phase 6 simulator authenticates as one registered Device, subscribes only to its configuration topic, publishes heartbeats, stores supported Sensor configurations in memory, and acknowledges them. It never publishes telemetry in Phase 6.

Provision credentials from Device Detail, then place the one-time values in the root environment or invoke Compose explicitly:

```bash
SIMULATOR_DEVICE_UID=ESP32-A8C339 \
SIMULATOR_MQTT_USERNAME='device:ESP32-A8C339' \
SIMULATOR_MQTT_PASSWORD='ONE_TIME_PASSWORD' \
docker compose --profile simulator up simulator
```

Set `SIMULATOR_FORCE_CONFIG_FAILURE=true` to make structurally valid configurations return a deterministic `FAILED` acknowledgement.
