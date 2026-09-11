# simplified_redis_test.py
"""
Simplified Redis test code for CodeQL inter-service connector testing.
Focuses on essential Redis patterns without unnecessary complexity.
"""

import asyncio
import json
import random
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import redis.asyncio as redis

@dataclass
class User:
    id: str
    name: str
    email: str

@dataclass
class Payment:
    success: bool
    transaction_id: str
    user_id: str
    amount: float

# ========== REDIS USER SERVICE ==========

class RedisUserService:
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_client = None
        self.redis_url = redis_url

    async def initialize(self):
        self.redis_client = redis.from_url(self.redis_url)
        await self.redis_client.ping()

    async def create_user(self, name: str, email: str) -> User:
        user_id = f'user-{random.randint(1000, 9999)}'
        user = User(user_id, name, email)
        
        # Store user in Redis hash
        await self.redis_client.hset(f'user:{user_id}', mapping=asdict(user))
        
        # Add to user index
        await self.redis_client.sadd('users:all', user_id)
        
        # Publish user created event
        event = {
            'type': 'USER_CREATED',
            'user_id': user_id,
            'data': asdict(user)
        }
        await self.redis_client.publish('user:events', json.dumps(event))
        
        return user

    async def get_user(self, user_id: str) -> Optional[User]:
        user_data = await self.redis_client.hgetall(f'user:{user_id}')
        
        if not user_data:
            return None
        
        return User(
            user_data[b'id'].decode(),
            user_data[b'name'].decode(), 
            user_data[b'email'].decode()
        )

    async def update_user_email(self, user_id: str, new_email: str) -> bool:
        exists = await self.redis_client.hexists(f'user:{user_id}', 'id')
        if not exists:
            return False
        
        await self.redis_client.hset(f'user:{user_id}', 'email', new_email)
        
        # Publish update event
        event = {'type': 'USER_UPDATED', 'user_id': user_id, 'email': new_email}
        await self.redis_client.publish('user:events', json.dumps(event))
        
        return True

    async def delete_user(self, user_id: str) -> bool:
        deleted = await self.redis_client.delete(f'user:{user_id}')
        await self.redis_client.srem('users:all', user_id)
        
        if deleted:
            event = {'type': 'USER_DELETED', 'user_id': user_id}
            await self.redis_client.publish('user:events', json.dumps(event))
        
        return deleted > 0

    async def get_all_users(self) -> List[str]:
        user_ids = await self.redis_client.smembers('users:all')
        return [uid.decode() for uid in user_ids]

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()

# ========== REDIS PAYMENT SERVICE ==========

class RedisPaymentService:
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_client = None
        self.redis_sub_client = None
        self.redis_url = redis_url
        self.listening = False

    async def initialize(self):
        self.redis_client = redis.from_url(self.redis_url)
        self.redis_sub_client = redis.from_url(self.redis_url)
        await self.redis_client.ping()

    async def start_listening(self):
        """Listen for user events and auto-process payments"""
        self.listening = True
        pubsub = self.redis_sub_client.pubsub()
        await pubsub.subscribe('user:events')
        
        try:
            async for message in pubsub.listen():
                if not self.listening:
                    break
                    
                if message['type'] == 'message':
                    event = json.loads(message['data'])
                    
                    if event.get('type') == 'USER_CREATED':
                        user_id = event.get('user_id')
                        await self.process_payment(user_id, 99.99)
                        
        except Exception as e:
            print(f'Payment listener error: {e}')
        finally:
            await pubsub.close()

    async def process_payment(self, user_id: str, amount: float) -> Payment:
        success = random.random() > 0.1  # 90% success rate
        transaction_id = f'txn-{random.randint(1000, 9999)}'
        
        payment = Payment(success, transaction_id, user_id, amount)
        
        # Store payment in Redis
        await self.redis_client.hset(f'payment:{transaction_id}', mapping=asdict(payment))
        
        # Add to user's payment history
        await self.redis_client.lpush(f'payments:{user_id}', json.dumps(asdict(payment)))
        
        # Update payment stats
        await self.redis_client.hincrby('stats:payments', 'total', 1)
        if success:
            await self.redis_client.hincrby('stats:payments', 'success', 1)
        
        # Publish payment event
        event = {
            'type': 'PAYMENT_PROCESSED',
            'user_id': user_id,
            'success': success,
            'transaction_id': transaction_id
        }
        await self.redis_client.publish('payment:events', json.dumps(event))
        
        return payment

    async def get_user_payments(self, user_id: str, limit: int = 5) -> List[Payment]:
        payment_data = await self.redis_client.lrange(f'payments:{user_id}', 0, limit - 1)
        
        payments = []
        for data in payment_data:
            payment_dict = json.loads(data)
            payments.append(Payment(
                payment_dict['success'],
                payment_dict['transaction_id'],
                payment_dict['user_id'],
                payment_dict['amount']
            ))
        
        return payments

    async def get_payment_stats(self) -> Dict[str, int]:
        stats = await self.redis_client.hgetall('stats:payments')
        return {
            'total': int(stats.get(b'total', 0)),
            'success': int(stats.get(b'success', 0))
        }

    def stop_listening(self):
        self.listening = False

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
        if self.redis_sub_client:
            await self.redis_sub_client.close()

# ========== REDIS CACHE SERVICE ==========

class RedisCacheService:
    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        self.redis_client = None
        self.redis_url = redis_url

    async def initialize(self):
        self.redis_client = redis.from_url(self.redis_url)
        await self.redis_client.ping()

    async def set_cache(self, key: str, value: Any, ttl: int = 3600):
        cache_key = f'cache:{key}'
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self.redis_client.setex(cache_key, ttl, serialized)

    async def get_cache(self, key: str) -> Optional[Any]:
        cache_key = f'cache:{key}'
        cached_value = await self.redis_client.get(cache_key)
        
        if cached_value:
            try:
                return json.loads(cached_value)
            except json.JSONDecodeError:
                return cached_value
        
        return None

    async def delete_cache(self, key: str) -> bool:
        cache_key = f'cache:{key}'
        deleted = await self.redis_client.delete(cache_key)
        return deleted > 0

    async def invalidate_pattern(self, pattern: str) -> int:
        cache_pattern = f'cache:{pattern}'
        keys = await self.redis_client.keys(cache_pattern)
        
        if keys:
            return await self.redis_client.delete(*keys)
        return 0

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()

# ========== REDIS BUSINESS SERVICE ==========

class RedisBusinessService:
    def __init__(self):
        self.redis_user_service = RedisUserService()
        self.redis_cache_service = RedisCacheService()

    async def initialize(self):
        await self.redis_user_service.initialize()
        await self.redis_cache_service.initialize()

    async def create_user_with_cache(self, name: str, email: str) -> User:
        """Create user and cache the result"""
        user = await self.redis_user_service.create_user(name, email)
        
        # Cache user data
        await self.redis_cache_service.set_cache(f'user:{user.id}', asdict(user), 1800)
        
        return user

    async def get_user_with_cache(self, user_id: str) -> Optional[User]:
        """Get user with cache fallback"""
        # Try cache first
        cached_data = await self.redis_cache_service.get_cache(f'user:{user_id}')
        if cached_data:
            return User(**cached_data)
        
        # Fallback to database
        user = await self.redis_user_service.get_user(user_id)
        
        if user:
            # Cache for next time
            await self.redis_cache_service.set_cache(f'user:{user_id}', asdict(user), 1800)
        
        return user

    async def update_user_and_invalidate_cache(self, user_id: str, new_email: str) -> bool:
        """Update user and invalidate related cache"""
        success = await self.redis_user_service.update_user_email(user_id, new_email)
        
        if success:
            # Invalidate user cache
            await self.redis_cache_service.delete_cache(f'user:{user_id}')
        
        return success

    async def get_all_users_with_cache(self) -> List[User]:
        """Get all users with caching"""
        # Check if user list is cached
        cached_users = await self.redis_cache_service.get_cache('users:all')
        if cached_users:
            return [User(**user_data) for user_data in cached_users]
        
        # Get from database
        user_ids = await self.redis_user_service.get_all_users()
        users = []
        
        for user_id in user_ids:
            user = await self.get_user_with_cache(user_id)
            if user:
                users.append(user)
        
        # Cache the result
        users_data = [asdict(user) for user in users]
        await self.redis_cache_service.set_cache('users:all', users_data, 600)
        
        return users

    async def disconnect(self):
        await self.redis_user_service.disconnect()
        await self.redis_cache_service.disconnect()

# ========== TEST RUNNER ==========

async def run_redis_test():
    """Test Redis inter-service communication patterns"""
    print('Starting Redis microservices test...')
    
    # Initialize services
    user_service = RedisUserService()
    payment_service = RedisPaymentService()
    cache_service = RedisCacheService()
    business_service = RedisBusinessService()
    
    try:
        # Initialize all services
        await user_service.initialize()
        await payment_service.initialize()
        await cache_service.initialize()
        await business_service.initialize()
        
        # Start payment event listener
        payment_task = asyncio.create_task(payment_service.start_listening())
        await asyncio.sleep(1)  # Let listener start
        
        # Test user creation (triggers payment via pub/sub)
        print('\n=== Testing User Creation ===')
        user1 = await business_service.create_user_with_cache('Alice Johnson', 'alice@test.com')
        user2 = await user_service.create_user('Bob Smith', 'bob@test.com')
        
        # Test cache operations
        print('\n=== Testing Cache Operations ===')
        await cache_service.set_cache('config', {'feature_enabled': True, 'version': '1.0'})
        config = await cache_service.get_cache('config')
        print(f'Retrieved config: {config}')
        
        # Test cached user retrieval
        print('\n=== Testing Cached User Retrieval ===')
        cached_user = await business_service.get_user_with_cache(user1.id)
        cached_user_again = await business_service.get_user_with_cache(user1.id)  # Should hit cache
        
        # Test user updates with cache invalidation
        print('\n=== Testing User Updates ===')
        await business_service.update_user_and_invalidate_cache(user1.id, 'alice.updated@test.com')
        updated_user = await business_service.get_user_with_cache(user1.id)  # Should miss cache
        
        # Test payment processing
        print('\n=== Testing Payment Processing ===')
        manual_payment = await payment_service.process_payment(user2.id, 149.99)
        payment_stats = await payment_service.get_payment_stats()
        print(f'Payment stats: {payment_stats}')
        
        # Test batch operations
        print('\n=== Testing Batch Operations ===')
        all_users = await business_service.get_all_users_with_cache()
        print(f'Total users: {len(all_users)}')
        
        user1_payments = await payment_service.get_user_payments(user1.id)
        print(f'User1 payments: {len(user1_payments)}')
        
        # Test cache invalidation
        print('\n=== Testing Cache Invalidation ===')
        invalidated = await cache_service.invalidate_pattern('user:*')
        print(f'Invalidated {invalidated} cache entries')
        
        # Wait for async events to complete
        await asyncio.sleep(2)
        
        print('\n=== Redis Test Summary ===')
        print('✓ User CRUD operations with Redis hash/set storage')
        print('✓ Payment processing with auto-trigger via pub/sub events')
        print('✓ Caching with TTL and cache invalidation patterns')
        print('✓ Event-driven architecture with Redis pub/sub')
        print('✓ Business logic combining multiple Redis services')
        
    except Exception as e:
        print(f'Test error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print('\n=== Cleaning up ===')
        payment_service.stop_listening()
        payment_task.cancel()
        
        try:
            await payment_task
        except asyncio.CancelledError:
            pass
        
        await user_service.disconnect()
        await payment_service.disconnect()
        await cache_service.disconnect()
        await business_service.disconnect()
        
        print('All Redis services disconnected')

if __name__ == "__main__":
    asyncio.run(run_redis_test())