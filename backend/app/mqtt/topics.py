import re
from dataclasses import dataclass
from typing import Literal

NAMESPACE = "aqress/pulse/v1/devices"
CONTROL_SUBSCRIPTIONS = (
    f"{NAMESPACE}/+/status",
    f"{NAMESPACE}/+/config/ack",
)


def status_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/status"


def config_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/config"


def config_ack_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/config/ack"


def telemetry_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/telemetry"


def command_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/command"


def command_ack_topic(device_uid: str) -> str:
    return f"{NAMESPACE}/{device_uid}/command/ack"


@dataclass(frozen=True)
class ParsedControlTopic:
    device_uid: str
    kind: Literal["status", "config_ack"]


CONTROL_TOPIC_PATTERN = re.compile(
    rf"^{re.escape(NAMESPACE)}/(?P<device_uid>[A-Z0-9][A-Z0-9._:-]*)/(?P<suffix>status|config/ack)$"
)


def parse_control_topic(topic: str) -> ParsedControlTopic | None:
    match = CONTROL_TOPIC_PATTERN.fullmatch(topic)
    if match is None:
        return None
    suffix = match.group("suffix")
    return ParsedControlTopic(
        device_uid=match.group("device_uid"),
        kind="status" if suffix == "status" else "config_ack",
    )
