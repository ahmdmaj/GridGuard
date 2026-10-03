import json
from typing import Callable, Dict, List, Any

TOPIC_TELEMETRY = "gridguard/plant/telemetry"
TOPIC_COMMAND = "gridguard/controller/command"

class MockMQTTBroker:
    def __init__(self) -> None:
        self.subscribers: Dict[str, List[Callable[[str], None]]] = {}

    def subscribe(self, topic: str, callback: Callable[[str], None]) -> None:
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    def publish(self, topic: str, payload_dict: Dict[str, Any]) -> None:
        payload_str = json.dumps(payload_dict)
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                callback(payload_str)
