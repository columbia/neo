# test_kafka_connector.py
import asyncio
import json
import random
import time
from typing import Dict, Any
from dataclasses import dataclass, asdict
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# ========== KAFKA EVENT SCHEMAS ==========

USER_EVENTS = {
    'USER_CREATED': 'user.created',
    'USER_UPDATED': 'user.updated'
}

PAYMENT_EVENTS = {
    'PAYMENT_REQUESTED': 'payment.requested',
    'PAYMENT_PROCESSED': 'payment.processed'
}

# ========== DATA TRANSFER OBJECTS ==========

@dataclass
class KafkaUserDto:
    id: str
    name: str
    email: str
    timestamp: float

@dataclass
class KafkaPaymentResult:
    success: bool
    transaction_id: str
    user_id: str
    amount: float
    timestamp: float

# ========== KAFKA PRODUCERS (Event Publishers) ==========

class UserKafkaService:
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.user_db: Dict[str, KafkaUserDto] = {}
    
    async def connect(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        await self.producer.start()
        print("KAFKA-USER-SVC: Producer connected")
    
    async def create_user(self, name: str, email: str) -> KafkaUserDto:
        print(f"KAFKA-USER-SVC: Creating user {name}")
        new_id = f"kafka-{len(self.user_db) + 1}"
        user = KafkaUserDto(new_id, name, email, time.time())
        self.user_db[new_id] = user
        
        # Publish user created event
        event_data = {
            'eventType': USER_EVENTS['USER_CREATED'],
            'userId': new_id,
            'userData': asdict(user)
        }
        
        await self.producer.send_and_wait(
            'user-events',
            value=event_data,
            key=new_id.encode('utf-8')
        )
        
        print(f"KAFKA-USER-SVC: Published USER_CREATED event for {new_id}")
        return user
    
    async def disconnect(self):
        if self.producer:
            await self.producer.stop()

class PaymentKafkaService:
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumer = None
        self.running = False
    
    async def connect(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        
        self.consumer = AIOKafkaConsumer(
            'user-events',
            bootstrap_servers=self.bootstrap_servers,
            group_id='payment-service-consumer',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        await self.producer.start()
        await self.consumer.start()
        print("KAFKA-PAYMENT-SVC: Producer and Consumer connected")
    
    async def start_listening(self):
        self.running = True
        async for msg in self.consumer:
            if not self.running:
                break
                
            event = msg.value
            
            if event.get('eventType') == USER_EVENTS['USER_CREATED']:
                user_id = event.get('userId')
                print(f"KAFKA-PAYMENT-SVC: Received USER_CREATED event for {user_id}")
                # Auto-trigger payment for new users
                await self.process_payment(user_id, 99.99)
    
    async def process_payment(self, user_id: str, amount: float) -> KafkaPaymentResult:
        print(f"KAFKA-PAYMENT-SVC: Processing payment of {amount} for user {user_id}")
        success = random.random() > 0.1  # 90% success rate
        transaction_id = f"txn-{random.randint(1000, 9999)}"
        
        result = KafkaPaymentResult(success, transaction_id, user_id, amount, time.time())
        
        # Publish payment processed event
        event_data = {
            'eventType': PAYMENT_EVENTS['PAYMENT_PROCESSED'],
            'userId': user_id,
            'amount': amount,
            'success': success,
            'transactionId': transaction_id,
            'timestamp': time.time()
        }
        
        await self.producer.send_and_wait(
            'payment-events',
            value=event_data,
            key=user_id.encode('utf-8')
        )
        
        print(f"KAFKA-PAYMENT-SVC: Published PAYMENT_PROCESSED event: {'SUCCESS' if success else 'FAILED'}")
        return result
    
    async def stop_listening(self):
        self.running = False
    
    async def disconnect(self):
        await self.stop_listening()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

# ========== KAFKA CONSUMER (Business Logic Orchestrator) ==========

class KafkaBusinessService:
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.consumer = None
        self.payment_results: Dict[str, Dict] = {}
        self.running = False
    
    async def connect(self):
        self.consumer = AIOKafkaConsumer(
            'user-events', 'payment-events',
            bootstrap_servers=self.bootstrap_servers,
            group_id='business-service-consumer',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        await self.consumer.start()
        print("KAFKA-BIZ: Consumer connected")
    
    async def start_listening(self):
        self.running = True
        async for msg in self.consumer:
            if not self.running:
                break
                
            event = msg.value
            
            if event.get('eventType') == USER_EVENTS['USER_CREATED']:
                user_id = event.get('userId')
                print(f"KAFKA-BIZ: User onboarding completed for {user_id}")
            
            elif event.get('eventType') == PAYMENT_EVENTS['PAYMENT_PROCESSED']:
                user_id = event.get('userId')
                success = event.get('success')
                print(f"KAFKA-BIZ: Payment flow completed for user {user_id} "
                      f"Result: {'SUCCESS' if success else 'FAILED'}")
                self.payment_results[user_id] = event
    
    async def onboard_new_user_and_make_payment(self, user_service: UserKafkaService, 
                                               name: str, email: str) -> KafkaUserDto:
        print(f"\nKAFKA-BIZ: Starting user onboarding flow for {name}")
        
        # Create user (this will trigger payment via event)
        user = await user_service.create_user(name, email)
        print(f"KAFKA-BIZ: User creation initiated for {user.id}")
        
        # In event-driven architecture, we don't wait synchronously
        # Payment will be processed via event listeners
        return user
    
    async def stop_listening(self):
        self.running = False
    
    async def disconnect(self):
        await self.stop_listening()
        if self.consumer:
            await self.consumer.stop()

# ========== TEST RUNNER ==========

async def run_kafka_test():
    print("Starting Kafka microservices test...")
    print("NOTE: This requires Kafka to be running on localhost:9092")
    
    user_service = UserKafkaService()
    payment_service = PaymentKafkaService()
    business_service = KafkaBusinessService()
    
    try:
        # Connect all services
        await user_service.connect()
        await payment_service.connect()
        await business_service.connect()
        
        # Start event listeners in background
        payment_task = asyncio.create_task(payment_service.start_listening())
        business_task = asyncio.create_task(business_service.start_listening())
        
        # Wait for consumers to be ready
        await asyncio.sleep(2)
        
        # Run business flow
        await business_service.onboard_new_user_and_make_payment(
            user_service,
            "Bob Wilson",
            "bob@kafka.com"
        )
        
        # Wait to see events flow through
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"KAFKA-TEST: Error: {e}")
    finally:
        # Cleanup
        await payment_service.stop_listening()
        await business_service.stop_listening()
        
        # Cancel background tasks
        payment_task.cancel()
        business_task.cancel()
        
        try:
            await payment_task
        except asyncio.CancelledError:
            pass
        
        try:
            await business_task
        except asyncio.CancelledError:
            pass
        
        # Disconnect services
        await user_service.disconnect()
        await payment_service.disconnect()
        await business_service.disconnect()

# Run test if this file is executed directly
if __name__ == "__main__":
    asyncio.run(run_kafka_test())