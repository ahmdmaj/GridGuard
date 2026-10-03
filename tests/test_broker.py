import json
import pytest
from telemetry.broker import MockMQTTBroker, TOPIC_TELEMETRY, TOPIC_COMMAND

def test_broker_subscribe_and_publish() -> None:
    broker = MockMQTTBroker()
    received_messages: list[str] = []
    
    def callback(payload: str) -> None:
        received_messages.append(payload)
        
    broker.subscribe(TOPIC_TELEMETRY, callback)
    
    mock_payload = {"status": "ok", "value": 42}
    broker.publish(TOPIC_TELEMETRY, mock_payload)
    
    assert len(received_messages) == 1
    received_str = received_messages[0]
    
    # Verify it's a JSON string, not a raw dict
    assert isinstance(received_str, str)
    
    # Verify it can be safely deserialized
    decoded = json.loads(received_str)
    assert decoded == mock_payload

def test_broker_topic_isolation() -> None:
    broker = MockMQTTBroker()
    telemetry_messages: list[str] = []
    command_messages: list[str] = []
    
    broker.subscribe(TOPIC_TELEMETRY, lambda msg: telemetry_messages.append(msg))
    broker.subscribe(TOPIC_COMMAND, lambda msg: command_messages.append(msg))
    
    broker.publish(TOPIC_TELEMETRY, {"test": "telemetry_data"})
    
    assert len(telemetry_messages) == 1
    assert len(command_messages) == 0
