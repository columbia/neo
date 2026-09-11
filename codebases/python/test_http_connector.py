# test_http_connector.py
import asyncio
import json
import random
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import uvicorn
from contextlib import asynccontextmanager

# ========== DATA TRANSFER OBJECTS ==========

@dataclass
class HttpUserDto:
    id: str
    name: str
    email: str

@dataclass
class HttpPaymentResult:
    success: bool
    transaction_id: str

class CreateHttpUserRequest(BaseModel):
    name: str
    email: str

class ProcessHttpPaymentRequest(BaseModel):
    user_id: str
    amount: float

# ========== HTTP SERVICE PROVIDERS (FastAPI Applications) ==========

class HttpUserService:
    def __init__(self):
        self.http_user_db: Dict[str, HttpUserDto] = {}
        self.app = FastAPI(title="HTTP User Service")
        self.setup_http_routes()
    
    def setup_http_routes(self):
        @self.app.get("/users/{user_id}")
        async def get_http_user_by_id(user_id: str):
            print(f"HTTP-USER-SVC: Received getHttpUserById for {user_id}")
            user = self.http_user_db.get(user_id, HttpUserDto("0", "Default", "default@http.com"))
            return asdict(user)
        
        @self.app.post("/users")
        async def create_http_user(request: CreateHttpUserRequest):
            print(f"HTTP-USER-SVC: Received createHttpUser for {request.name}")
            new_id = f"http-{len(self.http_user_db) + 1}"
            user = HttpUserDto(new_id, request.name, request.email)
            self.http_user_db[new_id] = user
            return asdict(user)

class HttpPaymentService:
    def __init__(self):
        self.app = FastAPI(title="HTTP Payment Service")
        self.setup_http_payment_routes()
    
    def setup_http_payment_routes(self):
        @self.app.post("/payments")
        async def process_http_payment(request: ProcessHttpPaymentRequest):
            print(f"HTTP-PAYMENT-SVC: Processing httpPayment of {request.amount} for user {request.user_id}")
            success = random.random() > 0.1  # 90% success rate
            result = HttpPaymentResult(success, f"http-txn-{random.randint(1000, 9999)}")
            return asdict(result)

# ========== HTTP CONSUMER (Business Logic Service) ==========

class HttpBusinessService:
    def __init__(self, http_user_service_url: str = "http://localhost:8001", 
                 http_payment_service_url: str = "http://localhost:8002"):
        self.http_user_service_url = http_user_service_url
        self.http_payment_service_url = http_payment_service_url
    
    async def onboard_http_user_and_make_payment(self, name: str, email: str, payment_amount: float):
        print(f"\nHTTP-BIZ: Starting http user onboarding flow for {name}")
        
        async with httpx.AsyncClient() as client:
            try:
                # 1. Call User service to create a user
                user_response = await client.post(
                    f"{self.http_user_service_url}/users",
                    json={"name": name, "email": email}
                )
                user_response.raise_for_status()
                new_user = user_response.json()
                print(f"HTTP-BIZ: Http user created with ID: {new_user['id']}")
                
                # 2. Call Payment service to process a payment for the new user
                if new_user and new_user.get('id'):
                    payment_response = await client.post(
                        f"{self.http_payment_service_url}/payments",
                        json={"user_id": new_user['id'], "amount": payment_amount}
                    )
                    payment_response.raise_for_status()
                    payment_result = payment_response.json()
                    print(f"HTTP-BIZ: Http payment result: {'SUCCESS' if payment_result['success'] else 'FAILED'}")
                    
            except httpx.HTTPError as e:
                print(f"HTTP-BIZ: Error in http onboarding flow: {e}")

# ========== SERVICE RUNNERS ==========

async def run_http_user_service():
    http_user_service = HttpUserService()
    config = uvicorn.Config(http_user_service.app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()

async def run_http_payment_service():
    http_payment_service = HttpPaymentService()
    config = uvicorn.Config(http_payment_service.app, host="127.0.0.1", port=8002, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()

# ========== TEST RUNNER ==========

async def run_http_test():
    print("Starting HTTP microservices test...")
    
    # Start services in background
    user_task = asyncio.create_task(run_http_user_service())
    payment_task = asyncio.create_task(run_http_payment_service())
    
    # Wait for services to start
    await asyncio.sleep(2)
    
    try:
        # Run business logic
        http_business_service = HttpBusinessService()
        await http_business_service.onboard_http_user_and_make_payment(
            "Alice Johnson", "alice@test.com", 99.99
        )
        
        # Wait a bit to see results
        await asyncio.sleep(1)
        
    finally:
        # Cleanup (in real scenarios, you'd handle graceful shutdown)
        user_task.cancel()
        payment_task.cancel()
        
        try:
            await user_task
        except asyncio.CancelledError:
            pass
        
        try:
            await payment_task
        except asyncio.CancelledError:
            pass

# Run test if this file is executed directly
if __name__ == "__main__":
    asyncio.run(run_http_test())