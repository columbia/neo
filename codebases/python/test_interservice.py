"""
Single file test for Python inter-service taint flow validation.
Run your CodeQL query on this file to validate Python outbound data transmission models.
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import requests
import httpx
import grpc
from kafka import KafkaProducer
import pika
import redis
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import asyncio
import aiohttp

app = FastAPI()

# Initialize clients
kafka_producer = KafkaProducer(bootstrap_servers=['localhost:9092'])
redis_client = redis.Redis(host='localhost', port=6379, db=0)
rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
rabbitmq_channel = rabbitmq_connection.channel()

# GraphQL client
graphql_transport = RequestsHTTPTransport(url="https://api.example.com/graphql")
graphql_client = Client(transport=graphql_transport)

# Data models
class UserRequest(BaseModel):
    name: str
    email: str

class User(BaseModel):
    id: str
    name: str
    role: str

class ApiResponse(BaseModel):
    data: str
    status: str

# Simulated gRPC stub
class UserServiceStub:
    def GetUser(self, request):
        return User(id=request.user_id, name="test", role="user")
    
    def ProcessData(self, request):
        return User(id="1", name="processed", role=request.data)

user_grpc_stub = UserServiceStub()

# TEST 1: HTTP Client Taint Flow - SHOULD BE DETECTED
@app.post("/test-http")
async def test_http_flow(user_input: str):
    # Requests library
    response = requests.get(f"https://api.example.com/{user_input}")
    return execute_privileged_operation(response.text)

# TEST 2: HTTP Client with JSON - SHOULD BE DETECTED
@app.post("/test-http-json")
async def test_http_json_flow(request: UserRequest):
    payload = {"query": request.name, "email": request.email}
    response = requests.post("https://api.example.com/users", json=payload)
    return execute_privileged_operation(response.json()["data"])

# TEST 3: HTTPX Async Client - SHOULD BE DETECTED
@app.post("/test-httpx")
async def test_httpx_flow(user_input: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/{user_input}")
    return execute_privileged_operation(response.text)

# TEST 4: aiohttp Client - SHOULD BE DETECTED
@app.post("/test-aiohttp")
async def test_aiohttp_flow(user_data: str):
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.example.com/process", 
                               json={"data": user_data}) as response:
            result = await response.text()
    return execute_privileged_operation(result)

# TEST 5: gRPC Service Call - SHOULD BE DETECTED
@app.post("/test-grpc")
async def test_grpc_flow(user_id: str):
    class UserRequest:
        def __init__(self, user_id):
            self.user_id = user_id
    
    request = UserRequest(user_id)
    user = user_grpc_stub.GetUser(request)
    return execute_privileged_operation(user.role)

# TEST 6: Kafka Producer - SHOULD BE DETECTED
@app.post("/test-kafka")
async def test_kafka_flow(message: str):
    kafka_producer.send('user-events', value=message.encode('utf-8'))
    return "Message sent to Kafka"

# TEST 7: RabbitMQ Publisher - SHOULD BE DETECTED
@app.post("/test-rabbitmq")
async def test_rabbitmq_flow(message: str):
    rabbitmq_channel.basic_publish(
        exchange='',
        routing_key='user-queue',
        body=message
    )
    return "Message sent to RabbitMQ"

# TEST 8: Redis Operations - SHOULD BE DETECTED
@app.post("/test-redis")
async def test_redis_flow(user_data: str):
    redis_client.set("user_data", user_data)
    redis_client.publish("user-channel", user_data)
    return "Data stored and published to Redis"

# TEST 9: GraphQL Query - SHOULD BE DETECTED
@app.post("/test-graphql")
async def test_graphql_flow(user_id: str):
    query = gql(f"""
        query {{
            user(id: "{user_id}") {{
                name
                role
            }}
        }}
    """)
    result = graphql_client.execute(query)
    return execute_privileged_operation(result["user"]["role"])

# TEST 10: GraphQL via HTTP - SHOULD BE DETECTED
@app.post("/test-graphql-http")
async def test_graphql_http_flow(query_input: str):
    graphql_query = {"query": f"{{ user(name: \"{query_input}\") {{ role }} }}"}
    response = requests.post("https://api.example.com/graphql", json=graphql_query)
    return execute_privileged_operation(response.json()["data"]["user"]["role"])

# TEST 11: Chained Inter-Service Calls - SHOULD BE DETECTED
@app.post("/test-chain")
async def test_chained_flow(user_input: str):
    # HTTP call
    http_response = requests.get(f"https://api.example.com/{user_input}")
    
    # gRPC call with HTTP response data
    class DataRequest:
        def __init__(self, data):
            self.data = data
    
    grpc_request = DataRequest(http_response.text)
    user = user_grpc_stub.ProcessData(grpc_request)
    
    # Kafka publish with gRPC result
    kafka_producer.send('processed-users', value=user.role.encode('utf-8'))
    
    return execute_privileged_operation(user.role)

# TEST 12: Multiple Outbound Calls - SHOULD BE DETECTED
@app.post("/test-multiple")
async def test_multiple_flow(user_data: str):
    # Send to multiple services
    requests.post("https://service1.example.com/users", json={"data": user_data})
    kafka_producer.send('user-topic', value=user_data.encode('utf-8'))
    redis_client.set(f"user:{user_data}", "processed")
    
    return "Data sent to multiple services"

# TEST 13: WebSocket Simulation - SHOULD BE DETECTED
@app.post("/test-websocket")
async def test_websocket_flow(message: str):
    # Simulating websocket send (would normally use websockets library)
    websocket_payload = {"type": "message", "data": message}
    response = requests.post("https://ws.example.com/send", json=websocket_payload)
    return execute_privileged_operation(response.text)

# TEST 14: Database ORM Simulation - SHOULD BE DETECTED
@app.post("/test-database")
async def test_database_flow(user_query: str):
    # Simulating database query (would normally use SQLAlchemy/etc)
    query_payload = {"sql": f"SELECT * FROM users WHERE name = '{user_query}'"}
    response = requests.post("https://db.example.com/query", json=query_payload)
    return execute_privileged_operation(response.json()["result"])

# TEST 15: Internal Data Only - SHOULD NOT BE DETECTED
@app.get("/test-internal")
async def test_internal_flow():
    internal_config = "internal-system-config"
    system_user = User(id="system", name="system", role="admin")
    return execute_privileged_operation(system_user.role)

# TEST 16: Hardcoded Values - SHOULD NOT BE DETECTED
@app.get("/test-hardcoded")
async def test_hardcoded_flow():
    hardcoded_data = "static-data"
    response = requests.get("https://api.example.com/config")
    # Using hardcoded data, not response data
    return execute_privileged_operation(hardcoded_data)

def execute_privileged_operation(data: str) -> str:
    """Simulates a security-sensitive operation"""
    return f"PRIVILEGED: {data}"

# Async version for testing async patterns
async def execute_privileged_operation_async(data: str) -> str:
    """Async version of privileged operation"""
    await asyncio.sleep(0.1)  # Simulate async work
    return f"PRIVILEGED: {data}"

"""
Expected Results:
✅ 14 flows should be detected (tests 1-14)
❌ 2 flows should NOT be detected (tests 15-16)

Test Categories:
- HTTP Clients: requests, httpx, aiohttp (tests 1-4)
- gRPC: protobuf service calls (test 5)
- Message Queues: Kafka, RabbitMQ (tests 6-7)
- Data Stores: Redis (test 8)
- GraphQL: direct and HTTP-based (tests 9-10)
- Complex Flows: chained calls, multiple outbound (tests 11-12)
- Other Protocols: WebSocket, Database (tests 13-14)
- Negative Cases: internal data only (tests 15-16)
"""