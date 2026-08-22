from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceState:
    started_monotonic: float
    sensor_configurations: dict[str, dict[str, Any]] = field(default_factory=dict)
