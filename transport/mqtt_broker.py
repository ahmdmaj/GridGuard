import json
import threading
from typing import Callable
import paho.mqtt.client as mqtt
from transport.base import Transport

class MqttBroker(Transport):
    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str = ""):
        self.host = host
        self.port = port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self.subscribers = {}
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            for topic in self.subscribers.keys():
                self.client.subscribe(topic)
                
    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except json.JSONDecodeError:
            return # Ignore malformed
            
        for sub_topic, callback in self.subscribers.items():
            # In a real impl, handle + and # wildcards. For now, exact match
            if sub_topic == topic:
                callback(topic, payload)
                
    def connect(self) -> None:
        self.client.connect(self.host, self.port)
        self.client.loop_start()
        
    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        
    def publish(self, topic: str, payload: dict, retain: bool = False, qos: int = 1) -> None:
        self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
        
    def subscribe(self, topic: str, callback: Callable[[str, dict], None]) -> None:
        self.subscribers[topic] = callback
        if self.client.is_connected():
            self.client.subscribe(topic)
