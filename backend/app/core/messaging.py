import json
from confluent_kafka import Producer, Consumer
from app.core.config import settings

def get_kafka_producer() -> Producer:
    conf = {
        'bootstrap.servers': settings.KAFKA_BROKERS,
        'client.id': 'ulp-producer'
    }
    return Producer(conf)

def get_kafka_consumer(group_id: str) -> Consumer:
    conf = {
        'bootstrap.servers': settings.KAFKA_BROKERS,
        'group.id': group_id,
        'auto.offset.reset': 'earliest'
    }
    return Consumer(conf)

def produce_event(producer: Producer, topic: str, key: str, value: dict):
    producer.produce(
        topic,
        key=key.encode('utf-8') if key else None,
        value=json.dumps(value).encode('utf-8')
    )
    producer.poll(0)
