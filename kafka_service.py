import os
import json
from dotenv import load_dotenv
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import numpy as np

load_dotenv()

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC")
SUCCESS_TOPIC = os.getenv("KAFKA_SUCCESS_TOPIC")
FAILURE_TOPIC = os.getenv("KAFKA_FAILURE_TOPIC")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP")



def ensure_json_serializable(obj):
    # Convert NumPy/Pandas types  for JSON serialization
    if isinstance(obj, (np.generic,)):  
        return obj.item()
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [ensure_json_serializable(v) for v in obj]
    return obj


class KafkaService:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.input_topic = os.getenv("KAFKA_INPUT_TOPIC", "wallet-transactions")
        self.success_topic = os.getenv("KAFKA_SUCCESS_TOPIC", "wallet-scores-success")
        self.failure_topic = os.getenv("KAFKA_FAILURE_TOPIC", "wallet-scores-failure")
        self.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "ai-scoring-service")

        # Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(ensure_json_serializable(v)).encode("utf-8"),
            retries=3
        )

        print(f"[KafkaService] Initialized with "
              f"bootstrap={self.bootstrap_servers}, input={self.input_topic}, "
              f"success={self.success_topic}, failure={self.failure_topic}")

    def consume(self):
        # Return a Kafka consumer for the input topic
        print(f"[KafkaService] Creating consumer for topic: {self.input_topic}")
        def m(parameter):
            #print("1.", parameter)
            try:
                return json.loads(parameter.decode("utf-8"))
            except:
                return None
        
 
        return KafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=m,
            auto_offset_reset="earliest",
            enable_auto_commit=True
        )

    def run_consumer(self, handler):
        # consume and process messages with the provided handler
        consumer = self.consume()
        for msg in consumer:
            try:
                print(f"[KafkaService] Consumed message from {self.input_topic}: {msg.value}")
                handler(msg.value)  
            except Exception as e:
                print(f"[KafkaService] ERROR while processing message: {e}")

    def produce(self, topic: str, message: dict):
        # Produce a message to Kafka
        try:
            safe_message = ensure_json_serializable(message)
            future = self.producer.send(topic, safe_message)
            future.get(timeout=10)  
            print(f"[KafkaService] Sent message to topic={topic}")
        except KafkaError as e:
            print(f"[KafkaService] Kafka error while producing to {topic}: {e}")
        except Exception as e:
            print(f"[KafkaService] Unexpected error while producing to {topic}: {e}")

    def close(self):
        # close producer
        try:
            self.producer.flush()
            self.producer.close()
            print("[KafkaService] Producer closed")
        except Exception:
            pass
