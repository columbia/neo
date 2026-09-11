# test_simplified_fastapi.py
import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Path, Body, status
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional
import random

# --- Simplified Models ---
# Using basic Pydantic models to define the data structures.

class User(BaseModel):
    id: str
    name: str
    email: EmailStr

class Payment(BaseModel):
    transaction_id: str
    user_id: str
    amount: float
    status: str

# --- In-Memory Databases ---
# Simple dictionaries to act as databases for our services.

user_db: Dict[str, User] = {}
payment_db: Dict[str, Payment] = {}
user_payments: Dict[str, List[Payment]] = {}

# --- Service Definitions ---
# Three separate FastAPI applications to simulate microservices.

user_service_app = FastAPI(title="User Service")
payment_service_app = FastAPI(title="Payment Service")
gateway_app = FastAPI(title="API Gateway")

# =======================================================================
# 1. USER SERVICE (Handles user data)
# =======================================================================

@user_service_app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(name: str = Body(...), email: EmailStr = Body(...)):
    """Creates a new user."""
    print(f"--> USER-SVC: Received request to create user '{name}'.")
    user_id = f"user_{random.randint(1000, 9999)}"
    new_user = User(id=user_id, name=name, email=email)
    user_db[user_id] = new_user
    print(f"<-- USER-SVC: Created user with ID {user_id}.")
    return new_user

@user_service_app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str = Path(..., description="The ID of the user to retrieve.")):
    """Retrieves a user by their ID."""
    print(f"--> USER-SVC: Received request to get user {user_id}.")
    if user_id not in user_db:
        print(f"<-- USER-SVC: User {user_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    print(f"<-- USER-SVC: Returning user {user_id}.")
    return user_db[user_id]

# =======================================================================
# 2. PAYMENT SERVICE (Handles payment data)
# =======================================================================

@payment_service_app.post("/payments", response_model=Payment, status_code=status.HTTP_201_CREATED)
async def process_payment(user_id: str = Body(...), amount: float = Body(...)):
    """Processes a new payment for a user."""
    print(f"--> PAYMENT-SVC: Received request to process payment for user {user_id}.")
    transaction_id = f"txn_{random.randint(10000, 99999)}"
    new_payment = Payment(
        transaction_id=transaction_id,
        user_id=user_id,
        amount=amount,
        status="completed"
    )
    payment_db[transaction_id] = new_payment
    if user_id not in user_payments:
        user_payments[user_id] = []
    user_payments[user_id].append(new_payment)
    print(f"<-- PAYMENT-SVC: Created payment {transaction_id}.")
    return new_payment

@payment_service_app.get("/users/{user_id}/payments", response_model=List[Payment])
async def get_user_payments(user_id: str = Path(..., description="The user ID.")):
    """Retrieves all payments for a specific user."""
    print(f"--> PAYMENT-SVC: Received request for payments of user {user_id}.")
    payments = user_payments.get(user_id, [])
    print(f"<-- PAYMENT-SVC: Returning {len(payments)} payments for user {user_id}.")
    return payments

# =======================================================================
# 3. API GATEWAY (The client that communicates with other services)
# =======================================================================

USER_SERVICE_URL = "http://localhost:8001"
PAYMENT_SERVICE_URL = "http://localhost:8002"

@gateway_app.post("/onboard")
async def onboard_user(name: str = Body(...), email: str = Body(...), initial_payment_amount: float = Body(...)):
    """
    SITUATION 1: Sequential Orchestration.
    The gateway first creates a user, then uses the new user's ID to make a payment.
    """
    print("\n>>> GATEWAY: Starting user onboarding flow.")
    async with httpx.AsyncClient() as client:
        # Step 1: Call User Service to create the user
        print("GATEWAY: Calling User Service to create user...")
        user_response = await client.post(
            f"{USER_SERVICE_URL}/users",
            json={"name": name, "email": email}
        )
        if user_response.status_code != 201:
            raise HTTPException(status_code=user_response.status_code, detail=user_response.json())
        
        new_user = user_response.json()
        user_id = new_user['id']
        print(f"GATEWAY: User service returned new user ID: {user_id}")

        # Step 2: Call Payment Service to process the initial payment
        print(f"GATEWAY: Calling Payment Service for user {user_id}...")
        payment_response = await client.post(
            f"{PAYMENT_SERVICE_URL}/payments",
            json={"user_id": user_id, "amount": initial_payment_amount}
        )
        if payment_response.status_code != 201:
            raise HTTPException(status_code=payment_response.status_code, detail=payment_response.json())
        
        new_payment = payment_response.json()
        print("<<< GATEWAY: Onboarding complete.")
        return {"user": new_user, "payment": new_payment}

@gateway_app.get("/profile/{user_id}")
async def get_full_profile(user_id: str):
    """
    SITUATION 2: Concurrent Orchestration.
    The gateway gets user details and payment history at the same time.
    """
    print(f"\n>>> GATEWAY: Getting full profile for user {user_id}.")
    async with httpx.AsyncClient() as client:
        # Define the two tasks to run concurrently
        print("GATEWAY: Calling User and Payment services concurrently...")
        user_task = client.get(f"{USER_SERVICE_URL}/users/{user_id}")
        payments_task = client.get(f"{PAYMENT_SERVICE_URL}/users/{user_id}/payments")

        # Run tasks in parallel and wait for both to complete
        user_response, payments_response = await asyncio.gather(
            user_task,
            payments_task
        )

        # SITUATION 3: Error Propagation
        if user_response.status_code != 200:
            print(f"GATEWAY: Error from User service: {user_response.status_code}")
            raise HTTPException(status_code=user_response.status_code, detail=user_response.json())

        if payments_response.status_code != 200:
            print(f"GATEWAY: Error from Payment service: {payments_response.status_code}")
            raise HTTPException(status_code=payments_response.status_code, detail=payments_response.json())

        print("<<< GATEWAY: Full profile retrieved successfully.")
        return {
            "user_details": user_response.json(),
            "payment_history": payments_response.json()
        }

# =======================================================================
# Main execution block to run the services and a test client
# =======================================================================

async def main():
    """Starts all microservices and runs a client to test the communication."""
    # Configure each service to run on a different port
    config_gateway = uvicorn.Config(gateway_app, host="localhost", port=8000, log_level="warning")
    config_user = uvicorn.Config(user_service_app, host="localhost", port=8001, log_level="warning")
    config_payment = uvicorn.Config(payment_service_app, host="localhost", port=8002, log_level="warning")

    server_gateway = uvicorn.Server(config_gateway)
    server_user = uvicorn.Server(config_user)
    server_payment = uvicorn.Server(config_payment)

    # Start all servers concurrently
    api_task = asyncio.gather(
        server_gateway.serve(),
        server_user.serve(),
        server_payment.serve()
    )

    # Give servers a moment to start up
    await asyncio.sleep(1)

    # --- Test Client ---
    try:
        async with httpx.AsyncClient() as client:
            print("--- CLIENT: Testing Sequential Onboarding ---")
            onboard_payload = {
                "name": "Jane Doe",
                "email": "jane.doe@example.com",
                "initial_payment_amount": 99.50
            }
            response = await client.post("http://localhost:8000/onboard", json=onboard_payload)
            response.raise_for_status()
            onboard_data = response.json()
            print("CLIENT: Onboarding successful. Response:", onboard_data, "\n")
            
            new_user_id = onboard_data['user']['id']

            print("--- CLIENT: Testing Concurrent Profile Fetch ---")
            response = await client.get(f"http://localhost:8000/profile/{new_user_id}")
            response.raise_for_status()
            print("CLIENT: Profile fetch successful. Response:", response.json(), "\n")

            print("--- CLIENT: Testing Not Found Error ---")
            response = await client.get("http://localhost:8000/profile/user_does_not_exist")
            print(f"CLIENT: Tested non-existent user. Status: {response.status_code}, Body: {response.json()}")


    except httpx.RequestError as e:
        print(f"CLIENT: An error occurred: {e}")
    finally:
        print("\n--- CLIENT: Test finished. Shutting down servers. ---")
        api_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())