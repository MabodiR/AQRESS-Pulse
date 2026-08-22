import random
from datetime import datetime
from typing import Any

from app.device_state import DeviceState
from app.sensor_generators import generate_sensor_values


def collect_due_readings(
    state: DeviceState,
    random_source: random.Random,
    *,
    now_monotonic: float,
    recorded_at: datetime,
) -> list[dict[str, Any]]:
    readings: list[dict[str, Any]] = []
    with state.lock:
        for sensor_uid, sensor in state.sensor_configurations.items():
            if not sensor.get("enabled", True):
                continue
            configuration = sensor.get("configuration", {})
            interval = configuration.get("sample_interval_seconds", 10)
            if isinstance(interval, bool) or not isinstance(interval, int | float):
                interval = 10
            last_sample = state.last_sampled_monotonic.get(sensor_uid)
            if last_sample is not None and now_monotonic - last_sample < max(
                float(interval), 0.1
            ):
                continue
            values = generate_sensor_values(sensor, state, random_source)
            enabled_channels = {
                channel.get("key")
                for channel in sensor.get("channels", [])
                if channel.get("enabled", True)
            }
            for channel, value in values.items():
                if channel not in enabled_channels:
                    continue
                readings.append(
                    {
                        "sensor_uid": sensor_uid,
                        "channel": channel,
                        "recorded_at": recorded_at.isoformat().replace("+00:00", "Z"),
                        "value": value,
                        "quality": "GOOD",
                    }
                )
            state.last_sampled_monotonic[sensor_uid] = now_monotonic
    return readings
