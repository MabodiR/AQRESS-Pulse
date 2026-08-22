from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class DeviceState:
    started_monotonic: float
    sensor_configurations: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_sampled_monotonic: dict[str, float] = field(default_factory=dict)
    last_values: dict[tuple[str, str], float | bool] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock, repr=False)
