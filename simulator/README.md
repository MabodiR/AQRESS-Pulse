# AQRESS Pulse Device Simulator

The Phase 7 simulator authenticates as one registered Device, subscribes only to its configuration topic, publishes heartbeats, stores and acknowledges supported Sensor configurations, and generates deterministic development telemetry for applied Sensors. Telemetry is batched, QoS 1, and never retained.

Provision credentials from Device Detail, then place the one-time values in the root environment or invoke Compose explicitly:

```bash
SIMULATOR_DEVICE_UID=ESP32-A8C339 \
SIMULATOR_MQTT_USERNAME='device:ESP32-A8C339' \
SIMULATOR_MQTT_PASSWORD='ONE_TIME_PASSWORD' \
docker compose --profile simulator up simulator
```

Set `SIMULATOR_FORCE_CONFIG_FAILURE=true` to make structurally valid configurations return a deterministic `FAILED` acknowledgement.

`SIMULATOR_RANDOM_SEED` controls repeatable generated values. The sampling loop honors each Sensor's `sample_interval_seconds`, Sensor and Channel enabled states, and applied configuration. DS18B20 and BME280 values vary gradually within realistic bounds; Digital Input toggles boolean state; Analog Input uses the configured engineering range or `0–100`.
