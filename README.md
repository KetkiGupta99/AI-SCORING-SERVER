# AI-SCORING-SERVER

##  Overview
This task implements a **Kafka-based microservice** that processes DeFi transaction data and calculates wallet reputation scores using AI logic.  

The system consumes wallet transactions from a Kafka topic, processes them through an AI model, and publishes results (success or failure) to output Kafka topics.  

##  Architecture
The system follows an **event-driven microservices architecture**:

1. **Producer** → sends wallet transaction data to Kafka (`wallet-transactions` topic)  
2. **Consumer Service** → consumes transactions, processes them with the AI scoring logic  
3. **Producer (results)** → sends results back to Kafka on:  
   - `wallet-scores-success` 
   - `wallet-scores-failure`

##  Project Structure
    dex-model.py # AI scoring model implementation
    types.py # Pydantic models for data validation
    kafka-service.py # Kafka consumer/producer
    main.py # FastAPI application entry point
    docker-compose.yml # service setup: Kafka, Zookeeper, MongoDB, API
    Dockerfile # Container configuration
    requirements.txt # Required Python packages
    .env file 
    test_challenge.py   # Test cases for validation

## Create and activate a virtual environment
    python3.11 -m venv venv
    venv\Scripts\activate

## Install dependencies: 
    pip install -r requirements.txt

## Create Environment File: 
    Create a .env file in the root directory with Kafka config

## Start Infrastructure with Docker: This task uses Docker-Compose.yml for Kafka, Zookeeper, MongoDB, and the FastAPI scoring service.
    Run: docker-compose up --build
    This will start:
    
    Zookeeper: Kafka coordination
    Kafka Broker: message streaming
    MongoDB: optional persistence
    AI Scoring Service (FastAPI): main microservice

## create topics 
    1. docker exec -it kafka /usr/bin/kafka-topics --create --topic wallet-transactions --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
    2. docker exec kafka /usr/bin/kafka-topics --create --topic wallet-scores-success --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
    3. docker exec kafka /usr/bin/kafka-topics --create --topic wallet-scores-failure --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
  
Verfiy topics are created or not:
   `docker exec kafka /usr/bin/kafka-topics --list --bootstrap-server localhost:9092`

1. Start the server:
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Run the test_challenges.py file for test cases:
   `python test_challenge.py`
3. Send test message to kafka:
   `docker exec -i -t kafka /usr/bin/kafka-console-producer --topic wallet-transactions --bootstrap-server localhost:9092`
   Paste Sample JSON message:
   `{"wallet_address":"0x742d35Cc6634C0532925a3b8D4C9db96590e4265","data":[{"protocolType":"dexes","transactions":[{"document_id":"507f1f77bcf86cd799439011","action":"swap","timestamp":1703980800,"caller":"0x742d35Cc6634C0532925a3b8D4C9db96590e4265","protocol":"uniswap_v3","poolId":"0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640","poolName":"Uniswap V3 USDC/WETH 0.05%","tokenIn":{"amount":1000000000,"amountUSD":1000.0,"address":"0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3","symbol":"USDC"},"tokenOut":{"amount":500000000000000000,"amountUSD":1000.0,"address":"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2","symbol":"WETH"}},{"document_id":"507f1f77bcf86cd799439012","action":"deposit","timestamp":1703980900,"caller":"0x742d35Cc6634C0532925a3b8D4C9db96590e4265","protocol":"uniswap_v3","poolId":"0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640","poolName":"Uniswap V3 USDC/WETH 0.05%","token0":{"amount":500000000,"amountUSD":500.0,"address":"0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3","symbol":"USDC"},"token1":{"amount":250000000000000000,"amountUSD":500.0,"address":"0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2","symbol":"WETH"}}]}]}`

4. Validate Output:
   Success topic:
   `docker exec -it kafka /usr/bin/kafka-console-consumer --topic wallet-scores-success --bootstrap-server localhost:9092 --from-beginning`
   Failure topic
   `docker exec -it kafka /usr/bin/kafka-console-consumer --topic wallet-scores-failure --bootstrap-server localhost:9092 --from-beginning`

   


    
    
