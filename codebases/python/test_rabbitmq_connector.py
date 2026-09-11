# test_rabbitmq_connector.py
import asyncio
import json
import random
import time
from typing import Dict, Callable
from dataclasses import dataclass, asdict
import aio_pika
from aio_pika import ExchangeType

# ========== RABBITMQ CONFIGURATION ==========

RABBITMQ_CONFIG = {
    'url': 'amqp://localhost:5672',
    'exchanges': {
        'RABBITMQ_USER_EVENTS': 'rabbitmq.user.events',
        'RABBITMQ_PAYMENT_EVENTS': 'rabbitmq.payment.events'
    },
    'queues': {
        'RABBITMQ_USER_CREATED': 'rabbitmq.user.created.queue',
        'RABBITMQ_PAYMENT_PROCESSING': 'rabbitmq.payment.processing.queue',
        'RABBITMQ_PAYMENT_COMPLETED': 'rabbitmq.payment.completed.queue',
        'RABBITMQ_BUSINESS_NOTIFICATIONS': 'rabbitmq.business.notifications.queue'
    },
    'routing_keys': {
        'RABBITMQ_USER_CREATED': 'rabbitmq.user.created',
        'RABBITMQ_PAYMENT_REQUESTED': 'rabbitmq.payment.requested',
        'RABBITMQ_PAYMENT_PROCESSED': 'rabbitmq.payment.processed'
    }
}

# ========== DATA TRANSFER OBJECTS ==========

@dataclass
class RabbitMQUserDto:
    id: str
    name: str
    email: str
    timestamp: float

@dataclass
class RabbitMQPaymentResult:
    success: bool
    transaction_id: str
    user_id: str
    amount: float
    timestamp: float

# ========== RABBITMQ BASE CLASS ==========

class RabbitMQServiceBase:
    def __init__(self):
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None

    async def connect_rabbitmq(self):
        try:
            self.rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_CONFIG['url'])
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()
            
            # Setup exchanges
            await self.rabbitmq_channel.declare_exchange(
                RABBITMQ_CONFIG['exchanges']['RABBITMQ_USER_EVENTS'], 
                ExchangeType.TOPIC, 
                durable=True
            )
            await self.rabbitmq_channel.declare_exchange(
                RABBITMQ_CONFIG['exchanges']['RABBITMQ_PAYMENT_EVENTS'], 
                ExchangeType.TOPIC, 
                durable=True
            )
            
            print('RabbitMQ connection established')
        except Exception as error:
            print(f'RabbitMQ connection failed: {error}')
            raise error

    async def disconnect_rabbitmq(self):
        if self.rabbitmq_channel:
            await self.rabbitmq_channel.close()
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()

    async def publish_rabbitmq_message(self, exchange: str, routing_key: str, message: dict):
        message_body = json.dumps(message).encode('utf-8')
        
        rabbitmq_exchange = await self.rabbitmq_channel.get_exchange(exchange)
        await rabbitmq_exchange.publish(
            aio_pika.Message(message_body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key
        )

    async def consume_rabbitmq_queue(self, queue_name: str, callback: Callable):
        rabbitmq_queue = await self.rabbitmq_channel.declare_queue(queue_name, durable=True)
        
        async def process_rabbitmq_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    content = json.loads(message.body.decode('utf-8'))
                    await callback(content, message)
                except Exception as error:
                    print(f'Error processing RabbitMQ message: {error}')

        await rabbitmq_queue.consume(process_rabbitmq_message)

# ========== RABBITMQ USER SERVICE (Publisher) ==========

class RabbitMQUserService(RabbitMQServiceBase):
    def __init__(self):
        super().__init__()
        self.rabbitmq_user_db: Dict[str, RabbitMQUserDto] = {}

    async def initialize_rabbitmq_user_service(self):
        await self.connect_rabbitmq()
        # Setup queues for this service
        await self.rabbitmq_channel.declare_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_USER_CREATED'], 
            durable=True
        )

    async def create_rabbitmq_user(self, name: str, email: str) -> RabbitMQUserDto:
        print(f'RABBITMQ-USER-SVC: Creating rabbitmq user {name}')
        new_id = f"rabbitmq-{len(self.rabbitmq_user_db) + 1}"
        rabbitmq_user = RabbitMQUserDto(new_id, name, email, time.time())
        self.rabbitmq_user_db[new_id] = rabbitmq_user

        # Publish user created event
        rabbitmq_message = {
            'eventType': 'RABBITMQ_USER_CREATED',
            'userId': new_id,
            'userData': asdict(rabbitmq_user)
        }

        await self.publish_rabbitmq_message(
            RABBITMQ_CONFIG['exchanges']['RABBITMQ_USER_EVENTS'],
            RABBITMQ_CONFIG['routing_keys']['RABBITMQ_USER_CREATED'],
            rabbitmq_message
        )

        print(f'RABBITMQ-USER-SVC: Published RABBITMQ_USER_CREATED event for {new_id}')
        return rabbitmq_user

    async def get_rabbitmq_user_by_id(self, user_id: str) -> RabbitMQUserDto:
        print(f'RABBITMQ-USER-SVC: Received getRabbitMQUserById for {user_id}')
        return self.rabbitmq_user_db.get(user_id) or RabbitMQUserDto('0', 'Default', 'default@rabbitmq.com', time.time())

# ========== RABBITMQ PAYMENT SERVICE (Consumer & Publisher) ==========

class RabbitMQPaymentService(RabbitMQServiceBase):
    def __init__(self):
        super().__init__()
        self.rabbitmq_is_listening = False

    async def initialize_rabbitmq_payment_service(self):
        await self.connect_rabbitmq()
        
        # Setup queues
        await self.rabbitmq_channel.declare_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_PAYMENT_PROCESSING'], 
            durable=True
        )
        await self.rabbitmq_channel.declare_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_PAYMENT_COMPLETED'], 
            durable=True
        )
        
        # Bind queues to exchanges
        rabbitmq_queue = await self.rabbitmq_channel.get_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_PAYMENT_PROCESSING']
        )
        rabbitmq_exchange = await self.rabbitmq_channel.get_exchange(
            RABBITMQ_CONFIG['exchanges']['RABBITMQ_USER_EVENTS']
        )
        await rabbitmq_queue.bind(
            rabbitmq_exchange,
            RABBITMQ_CONFIG['routing_keys']['RABBITMQ_USER_CREATED']
        )

    async def start_rabbitmq_listening(self):
        self.rabbitmq_is_listening = True
        print('RABBITMQ-PAYMENT-SVC: Started listening for rabbitmq events')

        async def handle_rabbitmq_message(message: dict, msg):
            if message.get('eventType') == 'RABBITMQ_USER_CREATED':
                print(f'RABBITMQ-PAYMENT-SVC: Received RABBITMQ_USER_CREATED event for {message.get("userId")}')
                # Auto-trigger payment for new users
                await self.process_rabbitmq_payment(message.get('userId'), 99.99)

        await self.consume_rabbitmq_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_PAYMENT_PROCESSING'], 
            handle_rabbitmq_message
        )

    async def process_rabbitmq_payment(self, user_id: str, amount: float) -> RabbitMQPaymentResult:
        print(f'RABBITMQ-PAYMENT-SVC: Processing rabbitmq payment of {amount} for user {user_id}')
        
        success = random.random() > 0.1  # 90% success rate
        transaction_id = f"rabbitmq-txn-{random.randint(1000, 9999)}"

        rabbitmq_result = RabbitMQPaymentResult(success, transaction_id, user_id, amount, time.time())

        # Publish payment processed event
        rabbitmq_message = {
            'eventType': 'RABBITMQ_PAYMENT_PROCESSED',
            'userId': user_id,
            'amount': amount,
            'success': success,
            'transactionId': transaction_id,
            'timestamp': time.time()
        }

        await self.publish_rabbitmq_message(
            RABBITMQ_CONFIG['exchanges']['RABBITMQ_PAYMENT_EVENTS'],
            RABBITMQ_CONFIG['routing_keys']['RABBITMQ_PAYMENT_PROCESSED'],
            rabbitmq_message
        )

        print(f'RABBITMQ-PAYMENT-SVC: Published RABBITMQ_PAYMENT_PROCESSED event: {"SUCCESS" if success else "FAILED"}')
        return rabbitmq_result

    def stop_rabbitmq_listening(self):
        self.rabbitmq_is_listening = False

# ========== RABBITMQ BUSINESS SERVICE (Consumer & Orchestrator) ==========

class RabbitMQBusinessService(RabbitMQServiceBase):
    def __init__(self):
        super().__init__()
        self.rabbitmq_payment_results: Dict[str, dict] = {}
        self.rabbitmq_is_listening = False

    async def initialize_rabbitmq_business_service(self):
        await self.connect_rabbitmq()
        
        # Setup business notification queue
        await self.rabbitmq_channel.declare_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_BUSINESS_NOTIFICATIONS'], 
            durable=True
        )
        
        # Bind to both user and payment events
        rabbitmq_queue = await self.rabbitmq_channel.get_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_BUSINESS_NOTIFICATIONS']
        )
        
        user_exchange = await self.rabbitmq_channel.get_exchange(
            RABBITMQ_CONFIG['exchanges']['RABBITMQ_USER_EVENTS']
        )
        payment_exchange = await self.rabbitmq_channel.get_exchange(
            RABBITMQ_CONFIG['exchanges']['RABBITMQ_PAYMENT_EVENTS']
        )
        
        await rabbitmq_queue.bind(user_exchange, 'rabbitmq.user.*')
        await rabbitmq_queue.bind(payment_exchange, 'rabbitmq.payment.*')

    async def start_rabbitmq_business_listening(self):
        self.rabbitmq_is_listening = True
        print('RABBITMQ-BIZ: Started listening for rabbitmq business events')

        async def handle_rabbitmq_business_message(message: dict, msg):
            if message.get('eventType') == 'RABBITMQ_USER_CREATED':
                print(f'RABBITMQ-BIZ: RabbitMQ user onboarding initiated for {message.get("userId")}')
            
            if message.get('eventType') == 'RABBITMQ_PAYMENT_PROCESSED':
                user_id = message.get('userId')
                success = message.get('success')
                print(f'RABBITMQ-BIZ: RabbitMQ payment flow completed for user {user_id} '
                      f'Result: {"SUCCESS" if success else "FAILED"}')
                self.rabbitmq_payment_results[user_id] = message

        await self.consume_rabbitmq_queue(
            RABBITMQ_CONFIG['queues']['RABBITMQ_BUSINESS_NOTIFICATIONS'],
            handle_rabbitmq_business_message
        )

    async def onboard_rabbitmq_user_and_make_payment(self, rabbitmq_user_service: RabbitMQUserService, 
                                                    name: str, email: str) -> RabbitMQUserDto:
        print(f'\nRABBITMQ-BIZ: Starting rabbitmq user onboarding flow for {name}')
        
        # Create user (this will trigger payment via message queue)
        rabbitmq_user = await rabbitmq_user_service.create_rabbitmq_user(name, email)
        print(f'RABBITMQ-BIZ: RabbitMQ user creation initiated for {rabbitmq_user.id}')
        
        # In message-driven architecture, we don't wait synchronously
        # Payment will be processed via RabbitMQ message queues
        return rabbitmq_user

    def stop_rabbitmq_business_listening(self):
        self.rabbitmq_is_listening = False

# ========== RABBITMQ RPC SERVICE (Request-Reply Pattern) ==========

class RabbitMQRPCService(RabbitMQServiceBase):
    def __init__(self):
        super().__init__()
        self.rabbitmq_reply_queue = None
        self.rabbitmq_pending_replies: Dict[str, asyncio.Future] = {}

    async def initialize_rabbitmq_rpc_service(self):
        await self.connect_rabbitmq()
        
        # Create reply queue for RPC responses
        self.rabbitmq_reply_queue = await self.rabbitmq_channel.declare_queue('', exclusive=True)
        
        # Listen for RPC replies
        async def handle_rabbitmq_rpc_reply(message: aio_pika.IncomingMessage):
            async with message.process():
                correlation_id = message.correlation_id
                future = self.rabbitmq_pending_replies.get(correlation_id)
                
                if future and not future.done():
                    response = json.loads(message.body.decode('utf-8'))
                    future.set_result(response)
                    del self.rabbitmq_pending_replies[correlation_id]

        await self.rabbitmq_reply_queue.consume(handle_rabbitmq_rpc_reply)

    async def make_rabbitmq_rpc_call(self, queue_name: str, request: dict, timeout: float = 5.0) -> dict:
        correlation_id = str(random.randint(100000, 999999))
        
        future = asyncio.Future()
        self.rabbitmq_pending_replies[correlation_id] = future

        # Send RPC request
        rabbitmq_queue = await self.rabbitmq_channel.declare_queue(queue_name)
        message_body = json.dumps(request).encode('utf-8')
        
        await self.rabbitmq_channel.default_exchange.publish(
            aio_pika.Message(
                message_body,
                correlation_id=correlation_id,
                reply_to=self.rabbitmq_reply_queue.name
            ),
            routing_key=queue_name
        )

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            if correlation_id in self.rabbitmq_pending_replies:
                del self.rabbitmq_pending_replies[correlation_id]
            raise Exception('RabbitMQ RPC call timeout')

# ========== TEST RUNNER ==========

async def run_rabbitmq_test():
    print('Starting RabbitMQ microservices test...')
    print('NOTE: This requires RabbitMQ to be running on localhost:5672')

    rabbitmq_user_service = RabbitMQUserService()
    rabbitmq_payment_service = RabbitMQPaymentService()
    rabbitmq_business_service = RabbitMQBusinessService()

    try:
        # Initialize all rabbitmq services
        await rabbitmq_user_service.initialize_rabbitmq_user_service()
        await rabbitmq_payment_service.initialize_rabbitmq_payment_service()
        await rabbitmq_business_service.initialize_rabbitmq_business_service()

        # Start rabbitmq event listeners
        payment_task = asyncio.create_task(rabbitmq_payment_service.start_rabbitmq_listening())
        business_task = asyncio.create_task(rabbitmq_business_service.start_rabbitmq_business_listening())

        # Wait for rabbitmq consumers to be ready
        await asyncio.sleep(2)

        # Run rabbitmq business flow
        await rabbitmq_business_service.onboard_rabbitmq_user_and_make_payment(
            rabbitmq_user_service,
            'Eve Davis',
            'eve@rabbitmq.com'
        )

        # Wait to see rabbitmq message flow through queues
        await asyncio.sleep(5)

    except Exception as error:
        print(f'RABBITMQ-TEST: Error: {error}')
    finally:
        # Cleanup
        rabbitmq_payment_service.stop_rabbitmq_listening()
        rabbitmq_business_service.stop_rabbitmq_business_listening()
        
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
        
        await rabbitmq_user_service.disconnect_rabbitmq()
        await rabbitmq_payment_service.disconnect_rabbitmq()
        await rabbitmq_business_service.disconnect_rabbitmq()

# Run test if this file is executed directly
if __name__ == "__main__":
    asyncio.run(run_rabbitmq_test())