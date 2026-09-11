// test_redis_connector.js
/**
 * Redis microservices communication patterns for CodeQL testing
 * Demonstrates: Pub/Sub, caching, distributed locking
 */

const redis = require('redis');
const { promisify } = require('util');

// ========== DATA MODELS ==========

class RedisUser {
    constructor(id, name, email) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.timestamp = Date.now();
    }
}

class RedisPayment {
    constructor(success, transactionId, userId, amount) {
        this.success = success;
        this.transactionId = transactionId;
        this.userId = userId;
        this.amount = amount;
        this.timestamp = Date.now();
    }
}

class RedisEvent {
    constructor(type, userId, data) {
        this.type = type;
        this.userId = userId;
        this.timestamp = Date.now();
        this.data = data;
    }
}

// ========== REDIS USER SERVICE ==========

class RedisUserService {
    constructor(redisUrl = 'redis://localhost:6379') {
        this.client = redis.createClient({ url: redisUrl });
        this.client.on('error', (err) => console.error('Redis Client Error', err));
    }

    async connect() {
        await this.client.connect();
        await this.client.ping();
        console.log('REDIS-USER-SVC: Connected');
    }

    async createUser(name, email) {
        console.log(`REDIS-USER-SVC: Creating user ${name}`);

        const userId = `redis-user-${Date.now()}`;
        const user = new RedisUser(userId, name, email);

        // Store user in Redis hash
        await this.client.hSet(`user:${userId}`, {
            id: user.id,
            name: user.name,
            email: user.email,
            timestamp: user.timestamp.toString()
        });

        // Add to user index
        await this.client.sAdd('users:all', userId);

        // Publish user created event
        const event = new RedisEvent('USER_CREATED', userId, user);
        await this.client.publish('user:events', JSON.stringify(event));

        console.log(`REDIS-USER-SVC: User created and event published: ${userId}`);
        return user;
    }

    async getUser(userId) {
        const userData = await this.client.hGetAll(`user:${userId}`);

        if (!userData || Object.keys(userData).length === 0) {
            return null;
        }

        return new RedisUser(
            userData.id,
            userData.name,
            userData.email
        );
    }

    async updateUser(userId, name, email) {
        const exists = await this.client.hExists(`user:${userId}`, 'id');
        if (!exists) {
            throw new Error('User not found');
        }

        // Update fields
        await this.client.hSet(`user:${userId}`, {
            name,
            email,
            timestamp: Date.now().toString()
        });

        // Publish update event
        const event = new RedisEvent('USER_UPDATED', userId, { name, email });
        await this.client.publish('user:events', JSON.stringify(event));

        console.log(`REDIS-USER-SVC: User updated: ${userId}`);
    }

    async deleteUser(userId) {
        const deleted = await this.client.del(`user:${userId}`);

        if (deleted === 0) {
            throw new Error('User not found');
        }

        // Remove from index
        await this.client.sRem('users:all', userId);

        // Publish delete event
        const event = new RedisEvent('USER_DELETED', userId, null);
        await this.client.publish('user:events', JSON.stringify(event));

        console.log(`REDIS-USER-SVC: User deleted: ${userId}`);
    }

    async getAllUsers() {
        return await this.client.sMembers('users:all');
    }

    async disconnect() {
        await this.client.quit();
    }

    getClient() {
        return this.client;
    }
}

// ========== REDIS PAYMENT SERVICE ==========

class RedisPaymentService {
    constructor(redisUrl = 'redis://localhost:6379') {
        this.client = redis.createClient({ url: redisUrl });
        this.subscriber = redis.createClient({ url: redisUrl });
        this.running = false;
    }

    async connect() {
        await this.client.connect();
        await this.subscriber.connect();
        console.log('REDIS-PAYMENT-SVC: Connected');
    }

    async startListening() {
        this.running = true;
        console.log('REDIS-PAYMENT-SVC: Started listening for events');

        await this.subscriber.subscribe('user:events', async (message) => {
            if (!this.running) return;

            try {
                const event = JSON.parse(message);

                if (event.type === 'USER_CREATED') {
                    const user = event.data;
                    console.log(`REDIS-PAYMENT-SVC: Received USER_CREATED event for ${user.id}`);
                    await this.processPayment(user.id, 99.99);
                }
            } catch (error) {
                console.error('Error processing event:', error);
            }
        });
    }

    async processPayment(userId, amount) {
        console.log(`REDIS-PAYMENT-SVC: Processing payment of ${amount} for user ${userId}`);

        const success = Math.random() > 0.1; // 90% success rate
        const payment = new RedisPayment(
            success,
            `redis-txn-${Date.now()}`,
            userId,
            amount
        );

        // Store payment
        const paymentKey = `payment:${payment.transactionId}`;
        await this.client.hSet(paymentKey, {
            success: payment.success.toString(),
            transaction_id: payment.transactionId,
            user_id: payment.userId,
            amount: payment.amount.toString(),
            timestamp: payment.timestamp.toString()
        });

        // Add to user's payment history
        await this.client.lPush(`payments:${userId}`, JSON.stringify(payment));

        // Update statistics
        await this.client.hIncrBy('stats:payments', 'total', 1);
        if (success) {
            await this.client.hIncrBy('stats:payments', 'success', 1);
        }

        // Publish payment event
        const event = new RedisEvent('PAYMENT_PROCESSED', userId, payment);
        await this.client.publish('payment:events', JSON.stringify(event));

        console.log(`REDIS-PAYMENT-SVC: Payment processed: ${payment.transactionId}`);
        return payment;
    }

    async getUserPayments(userId, limit = 5) {
        const paymentData = await this.client.lRange(`payments:${userId}`, 0, limit - 1);
        return paymentData.map(data => JSON.parse(data));
    }

    async getPaymentStats() {
        const stats = await this.client.hGetAll('stats:payments');
        return {
            total: parseInt(stats.total || 0),
            success: parseInt(stats.success || 0)
        };
    }

    stopListening() {
        this.running = false;
    }

    async disconnect() {
        this.stopListening();
        await this.subscriber.unsubscribe();
        await this.subscriber.quit();
        await this.client.quit();
    }
}

// ========== REDIS CACHE SERVICE ==========

class RedisCacheService {
    constructor(redisUrl = 'redis://localhost:6379', dbIndex = 1) {
        this.client = redis.createClient({ 
            url: redisUrl,
            database: dbIndex 
        });
    }

    async connect() {
        await this.client.connect();
        console.log('REDIS-CACHE-SVC: Connected');
    }

    async setCache(key, value, ttl = 3600) {
        const cacheKey = `cache:${key}`;
        const data = typeof value === 'string' ? value : JSON.stringify(value);
        await this.client.setEx(cacheKey, ttl, data);
    }

    async getCache(key) {
        const cacheKey = `cache:${key}`;
        const cached = await this.client.get(cacheKey);

        if (!cached) return null;

        try {
            return JSON.parse(cached);
        } catch {
            return cached;
        }
    }

    async deleteCache(key) {
        const cacheKey = `cache:${key}`;
        return await this.client.del(cacheKey);
    }

    async invalidatePattern(pattern) {
        const cachePattern = `cache:${pattern}`;
        const keys = await this.client.keys(cachePattern);

        if (keys.length > 0) {
            return await this.client.del(keys);
        }

        return 0;
    }

    async disconnect() {
        await this.client.quit();
    }
}

// ========== REDIS BUSINESS SERVICE ==========

class RedisBusinessService {
    constructor(redisUrl = 'redis://localhost:6379', userService, cacheService) {
        this.userService = userService;
        this.cacheService = cacheService;
        this.client = redis.createClient({ url: redisUrl });
        this.subscriber = redis.createClient({ url: redisUrl });
        this.results = new Map();
        this.running = false;
    }

    async connect() {
        await this.client.connect();
        await this.subscriber.connect();
        console.log('REDIS-BIZ: Connected');
    }

    async startListening() {
        this.running = true;
        console.log('REDIS-BIZ: Started listening for business events');

        // Subscribe to user events
        await this.subscriber.subscribe('user:events', async (message) => {
            if (!this.running) return;

            const event = JSON.parse(message);
            if (event.type === 'USER_CREATED') {
                console.log(`REDIS-BIZ: User onboarding initiated for ${event.userId}`);
            }
        });

        // Subscribe to payment events
        await this.subscriber.subscribe('payment:events', async (message) => {
            if (!this.running) return;

            const event = JSON.parse(message);
            if (event.type === 'PAYMENT_PROCESSED') {
                const payment = event.data;
                this.results.set(payment.userId, payment);
                console.log(`REDIS-BIZ: Payment flow completed for user ${payment.userId} - SUCCESS`);
            }
        });
    }

    async createUserWithCache(name, email) {
        const user = await this.userService.createUser(name, email);

        // Cache user data
        await this.cacheService.setCache(`user:${user.id}`, user, 1800);

        return user;
    }

    async getUserWithCache(userId) {
        // Try cache first
        const cached = await this.cacheService.getCache(`user:${userId}`);
        if (cached) {
            console.log(`REDIS-BIZ: Cache hit for user ${userId}`);
            return cached;
        }

        // Fallback to database
        const user = await this.userService.getUser(userId);

        if (user) {
            // Cache for next time
            await this.cacheService.setCache(`user:${userId}`, user, 1800);
            console.log(`REDIS-BIZ: Cache miss for user ${userId}, cached now`);
        }

        return user;
    }

    async updateUserAndInvalidateCache(userId, name, email) {
        await this.userService.updateUser(userId, name, email);

        // Invalidate cache
        await this.cacheService.deleteCache(`user:${userId}`);
    }

    getPaymentResult(userId) {
        return this.results.get(userId);
    }

    stopListening() {
        this.running = false;
    }

    async disconnect() {
        this.stopListening();
        await this.subscriber.unsubscribe();
        await this.subscriber.quit();
        await this.client.quit();
    }
}

// ========== REDIS DISTRIBUTED LOCK ==========

class RedisDistributedLock {
    constructor(client, resource, ttl = 5000) {
        this.client = client;
        this.key = `lock:${resource}`;
        this.value = `${Date.now()}-${Math.random()}`;
        this.ttl = ttl;
    }

    async acquire() {
        const result = await this.client.set(this.key, this.value, {
            PX: this.ttl,
            NX: true
        });

        return result === 'OK';
    }

    async release() {
        // Lua script to ensure we only delete our own lock
        const script = `
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
        `;

        await this.client.eval(script, {
            keys: [this.key],
            arguments: [this.value]
        });
    }
}

// ========== REDIS RATE LIMITER ==========

class RedisRateLimiter {
    constructor(client, maxRequests = 100, windowMs = 60000) {
        this.client = client;
        this.maxRequests = maxRequests;
        this.windowMs = windowMs;
    }

    async checkLimit(userId) {
        const key = `ratelimit:${userId}`;
        const now = Date.now();
        const windowStart = now - this.windowMs;

        // Remove old entries
        await this.client.zRemRangeByScore(key, 0, windowStart);

        // Count requests in current window
        const count = await this.client.zCard(key);

        if (count >= this.maxRequests) {
            return false; // Rate limit exceeded
        }

        // Add current request
        await this.client.zAdd(key, { score: now, value: `${now}` });
        await this.client.expire(key, Math.ceil(this.windowMs / 1000));

        return true; // Request allowed
    }
}

// ========== TEST RUNNER ==========

async function runRedisTests() {
    console.log('Starting Redis microservices test...');
    console.log('NOTE: This requires Redis to be running on localhost:6379\n');

    const userService = new RedisUserService();
    const paymentService = new RedisPaymentService();
    const cacheService = new RedisCacheService();
    const businessService = new RedisBusinessService('redis://localhost:6379', userService, cacheService);

    try {
        // Connect all services
        await userService.connect();
        await paymentService.connect();
        await cacheService.connect();
        await businessService.connect();

        // Start event listeners
        await paymentService.startListening();
        await businessService.startListening();

        // Wait for subscribers to be ready
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Test user creation with cache
        console.log('--- Testing User Creation with Cache ---');
        const user = await businessService.createUserWithCache('Hannah', 'hannah@redis.com');

        // Test cached retrieval
        console.log('\n--- Testing Cached User Retrieval ---');
        const cachedUser = await businessService.getUserWithCache(user.id);
        const cachedUserAgain = await businessService.getUserWithCache(user.id); // Should hit cache

        // Test update with cache invalidation
        console.log('\n--- Testing User Update ---');
        await businessService.updateUserAndInvalidateCache(user.id, 'Hannah Updated', 'hannah.updated@redis.com');
        const updatedUser = await businessService.getUserWithCache(user.id); // Should miss cache

        // Wait for payment events
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Check payment result
        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`\nPayment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        // Test distributed lock
        console.log('\n--- Testing Distributed Lock ---');
        const lock = new RedisDistributedLock(userService.getClient(), 'test-resource', 5000);
        const acquired = await lock.acquire();
        console.log(`Lock acquired: ${acquired}`);
        if (acquired) {
            await lock.release();
            console.log('Lock released');
        }

        // Test cache invalidation
        console.log('\n--- Testing Cache Invalidation ---');
        const deleted = await cacheService.invalidatePattern('user:*');
        console.log(`Invalidated ${deleted} cache entries`);

        // Test payment stats
        const stats = await paymentService.getPaymentStats();
        console.log('\nPayment stats:', stats);

        console.log('\n=== Redis Test Summary ===');
        console.log('✓ Pub/Sub event-driven communication');
        console.log('✓ Caching with TTL and invalidation');
        console.log('✓ Distributed locking');
        console.log('✓ Hash storage for structured data');
        console.log('✓ List storage for payment history');
        console.log('✓ Set storage for user index');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        // Cleanup
        paymentService.stopListening();
        businessService.stopListening();

        await userService.disconnect();
        await paymentService.disconnect();
        await cacheService.disconnect();
        await businessService.disconnect();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runRedisTests().catch(console.error);
}

module.exports = {
    RedisUser,
    RedisPayment,
    RedisEvent,
    RedisUserService,
    RedisPaymentService,
    RedisCacheService,
    RedisBusinessService,
    RedisDistributedLock,
    RedisRateLimiter
};