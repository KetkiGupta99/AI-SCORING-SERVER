
import time
import asyncio
import os
import threading
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import numpy as np
from app.utils.types import WalletInput, WalletScoreResult
from app.models.dex_model import process_wallet
from app.services.kafka_service import KafkaService

app = FastAPI(title="Wallet Scoring API")

SERVICE_START_TIME: float = time.time()
processed_wallets_counter: int = 0

# Kafka service 
kafka_service: Optional[KafkaService] = None

#  Utilities 

def ensure_json_serializable(obj: Any) -> Any:
    # Convert numpy types and nested structures to JSON-serializable types
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [ensure_json_serializable(v) for v in obj]
    return obj

# API Endpoints 

@app.get("/")
def home() -> Dict[str, str]:
    return {
        "service": os.getenv("SERVICE_NAME", "Wallet Scoring API"),
        "message": "Wallet Scoring API is running. Use POST /score-wallet to score wallets."
    }

@app.get("/api/v1/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/api/v1/stats")
async def stats() -> Dict[str, Union[int, str]]:
    uptime_seconds: int = int(time.time() - SERVICE_START_TIME)
    return {
        "status": "ok",
        "processed_wallets": processed_wallets_counter,
        "uptime_seconds": uptime_seconds
    }

# Request Models 

class WalletTransaction(BaseModel):
    wallet_address: str
    data: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

# Wallet Scoring Endpoint 

@app.post("/score-wallet")
async def score_wallet(wallet: WalletInput) -> WalletScoreResult:
    global processed_wallets_counter
    start_time = time.time()
    try:
        result = process_wallet(wallet.model_dump())
        await asyncio.sleep(0.001)  

        processing_time_ms: int = int((time.time() - start_time) * 1000)
        processed_wallets_counter += 1

        result["processing_time_ms"] = processing_time_ms
        result["timestamp"] = int(time.time())

        print(f"[INFO] Processed wallet {wallet.get('wallet_address', 'unknown')} in {processing_time_ms} ms")
        return ensure_json_serializable(result)

    except Exception as e:
        print(f"[ERROR] Failed to score wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

#  Kafka Consumer Loop 

def consume_loop() -> None:
    # Kafka consumer loop to process wallet messages
    global processed_wallets_counter, kafka_service
    if not kafka_service:
        print("[ERROR] Kafka service not initialized")
        return

    consumer = kafka_service.consume()
    print("[INFO] Kafka consumer loop started")

    for msg in consumer:
        try:
            wallet: Dict[str, Any] = msg.value
            print(f"[INFO] Consumed message: {wallet.get('wallet_address', 'unknown')}")

            result: WalletScoreResult = process_wallet(wallet)
            result["timestamp"] = int(time.time())
            kafka_service.produce(kafka_service.success_topic, result)

            processed_wallets_counter += 1
            print(f"[INFO] Produced result for wallet {wallet.get('wallet_address', 'unknown')}")
        except Exception as e:
            error_msg = {"error": str(e), "wallet": msg.value}
            kafka_service.produce(kafka_service.failure_topic, error_msg)
            print(f"[ERROR] Failed processing Kafka message: {e}")

#  Startup Event 

@app.on_event("startup")
def start_consumer() -> None:
    global kafka_service
    retries: int = 5
    for attempt in range(retries):
        try:
            kafka_service = KafkaService()
            thread = threading.Thread(target=consume_loop, daemon=True)
            thread.start()
            print("[INFO] Kafka consumer thread started")
            return
        except Exception as e:
            print(f"[WARNING] Kafka not ready (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(5)
    print("[ERROR] Could not connect to Kafka after retries")
