import logging
import time

from app.device_state import DeviceState
from app.mqtt_client import SimulatorMqttClient
from app.settings import SimulatorSettings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> None:
    settings = SimulatorSettings()
    settings.validate()
    SimulatorMqttClient(settings, DeviceState(started_monotonic=time.monotonic())).run()


if __name__ == "__main__":
    main()
