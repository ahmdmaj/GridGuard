import json
from typing import Callable
from transport.base import Transport

class MockBroker(Transport):
    def __init__(self):
        self.subscribers = {}
        self.retained = {}
        
    def connect(self) -> None:
        pass
        
    def disconnect(self) -> None:
        pass
        
    def publish(self, topic: str, payload: dict, retain: bool = False, qos: int = 1) -> None:
        if retain:
            self.retained[topic] = payload
            
        for sub_topic, callback in self.subscribers.items():
            if self._topic_matches(sub_topic, topic):
                # Copy payload to simulate network serialization
                callback(topic, json.loads(json.dumps(payload)))
                
    def subscribe(self, topic: str, callback: Callable[[str, dict], None]) -> None:
        self.subscribers[topic] = callback
        
        # Deliver retained messages
        for ret_topic, payload in self.retained.items():
            if self._topic_matches(topic, ret_topic):
                callback(ret_topic, json.loads(json.dumps(payload)))
                
    def _topic_matches(self, sub_topic: str, pub_topic: str) -> bool:
        # Simple exact match (no wildcards in mock for now)
        return sub_topic == pub_topic
