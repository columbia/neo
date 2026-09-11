// test_interservice_chain.js
/**
 * Complex multi-protocol communication chains for CodeQL testing
 * Demonstrates: Cross-protocol flows, taint propagation, privileged operations
 */

const axios = require('axios');
const { Kafka } = require('kafkajs');
const amqp = require('amqplib');
const redis = require('redis');

// ========== CHAINED SERVICE ORCHESTRATOR ==========

class ChainedServiceOrchestrator {
    constructor() {
        this.httpUserServiceUrl = 'http://localhost:8001';
        this.httpPaymentServiceUrl = 'http://localhost:8002';
        this.kafkaBrokers = ['localhost:9092'];
        this.rabbitmqUrl = 'amqp://localhost:5672';
        this.redisUrl = 'redis://localhost:6379';
        
        // Initialize clients
        this.kafka = new Kafka({ clientId: 'orchestrator', brokers: this.kafkaBrokers });
        this.kafkaProducer = this.kafka.producer();
        this.redisClient = null;
        this.rabbitmqConnection = null;
        this.rabbitmqChannel = null;
    }

    async initialize() {
        // Connect Kafka
        await this.kafkaProducer.connect();
        
        // Connect Redis
        this.redisClient = redis.createClient({ url: this.redisUrl });
        await this.redisClient.connect();
        
        // Connect RabbitMQ
        this.rabbitmqConnection = await amqp.connect(this.rabbitmqUrl);
        this.rabbitmqChannel = await this.rabbitmqConnection.createChannel();
        
        console.log('Orchestrator initialized with all protocols');
    }

    // PATTERN 1: HTTP → gRPC → Kafka Chain - SHOULD BE DETECTED
    async httpToGrpcToKafkaChain(name, email, amount) {
        console.log('\n=== CHAIN PATTERN 1: HTTP → gRPC → Kafka ===');

        try {
            // Step 1: HTTP call
            const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, {
                name,
                email
            });
            const httpUser = httpResponse.data;
            console.log(`HTTP step: Created user ${httpUser.id}`);

            // Step 2: gRPC call (simulated - would be actual gRPC in production)
            const grpcUser = {
                id: `grpc-${httpUser.id}`,
                name: httpUser.name,
                email: httpUser.email
            };
            console.log(`gRPC step: Processed user ${grpcUser.id}`);

            // Step 3: Kafka publish
            await this.kafkaProducer.send({
                topic: 'user-events',
                messages: [{
                    key: grpcUser.id,
                    value: JSON.stringify({
                        eventType: 'USER_CREATED',
                        userId: grpcUser.id,
                        data: grpcUser
                    })
                }]
            });
            console.log(`Kafka step: Published event for ${grpcUser.id}`);

            return { httpUser, grpcUser };
        } catch (error) {
            console.error('Chain failed:', error.message);
            throw error;
        }
    }

    // PATTERN 2: gRPC → Redis → RabbitMQ Chain - SHOULD BE DETECTED
    async grpcToRedisToRabbitMQChain(name, email) {
        console.log('\n=== CHAIN PATTERN 2: gRPC → Redis → RabbitMQ ===');

        try {
            // Step 1: gRPC call (simulated)
            const grpcUser = {
                id: `grpc-user-${Date.now()}`,
                name,
                email
            };
            console.log(`gRPC step: Created user ${grpcUser.id}`);

            // Step 2: Store in Redis
            await this.redisClient.hSet(`user:${grpcUser.id}`, {
                id: grpcUser.id,
                name: grpcUser.name,
                email: grpcUser.email
            });
            console.log(`Redis step: Stored user ${grpcUser.id}`);

            // Step 3: Publish to RabbitMQ
            await this.rabbitmqChannel.assertExchange('user-events', 'topic', { durable: true });
            const message = Buffer.from(JSON.stringify({
                eventType: 'USER_CREATED',
                userId: grpcUser.id,
                data: grpcUser
            }));
            this.rabbitmqChannel.publish('user-events', 'user.created', message);
            console.log(`RabbitMQ step: Published event for ${grpcUser.id}`);

            return grpcUser;
        } catch (error) {
            console.error('Chain failed:', error.message);
            throw error;
        }
    }

    // PATTERN 3: Fan-Out to Multiple Services - SHOULD BE DETECTED
    async fanOutPattern(name, email) {
        console.log('\n=== CHAIN PATTERN 3: Fan-Out to Multiple Services ===');

        const promises = [
            // HTTP call
            axios.post(`${this.httpUserServiceUrl}/users`, { name, email })
                .then(res => ({ protocol: 'HTTP', user: res.data })),
            
            // Kafka publish
            this.kafkaProducer.send({
                topic: 'user-events',
                messages: [{
                    value: JSON.stringify({ name, email })
                }]
            }).then(() => ({ protocol: 'Kafka', success: true })),
            
            // Redis store
            this.redisClient.hSet(`temp:user:${Date.now()}`, { name, email })
                .then(() => ({ protocol: 'Redis', success: true }))
        ];

        try {
            const results = await Promise.all(promises);
            console.log('Fan-out completed:', results.map(r => r.protocol).join(', '));
            return results;
        } catch (error) {
            console.error('Fan-out failed:', error.message);
            throw error;
        }
    }

    // PATTERN 4: Conditional Protocol Routing - SHOULD BE DETECTED
    async conditionalRouting(userType, name, email) {
        console.log(`\n=== CHAIN PATTERN 4: Conditional Protocol Routing (${userType}) ===`);

        switch (userType) {
            case 'premium':
                // Premium users: HTTP → gRPC → Redis
                const httpUser = await axios.post(`${this.httpUserServiceUrl}/users`, {
                    name: `Premium ${name}`,
                    email
                });
                
                const grpcData = { ...httpUser.data, premium: true };
                
                await this.redisClient.hSet(`premium:user:${httpUser.data.id}`, 
                    JSON.stringify(grpcData));
                
                console.log('Premium routing: HTTP → gRPC → Redis');
                return grpcData;

            case 'standard':
                // Standard users: Kafka → RabbitMQ
                await this.kafkaProducer.send({
                    topic: 'user-events',
                    messages: [{ value: JSON.stringify({ name, email }) }]
                });

                const rabbitMsg = Buffer.from(JSON.stringify({ name, email }));
                await this.rabbitmqChannel.assertQueue('standard-users');
                this.rabbitmqChannel.sendToQueue('standard-users', rabbitMsg);

                console.log('Standard routing: Kafka → RabbitMQ');
                return { type: 'standard', name, email };

            default:
                // Basic users: HTTP only
                const basicUser = await axios.post(`${this.httpUserServiceUrl}/users`, {
                    name,
                    email
                });
                console.log('Basic routing: HTTP only');
                return basicUser.data;
        }
    }

    // PATTERN 5: Batch Processing Loop - SHOULD BE DETECTED
    async batchProcessingLoop(users) {
        console.log(`\n=== CHAIN PATTERN 5: Batch Loop Processing (${users.length} users) ===`);

        const results = [];

        for (let i = 0; i < users.length; i++) {
            const user = users[i];
            console.log(`Processing user ${i + 1}/${users.length}: ${user.name}`);

            try {
                // HTTP call
                const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, user);
                
                // Kafka publish
                await this.kafkaProducer.send({
                    topic: 'user-events',
                    messages: [{
                        value: JSON.stringify(httpResponse.data)
                    }]
                });

                results.push({ success: true, user: httpResponse.data });
            } catch (error) {
                console.error(`Failed to process ${user.name}:`, error.message);
                results.push({ success: false, user });
            }
        }

        console.log(`Batch processing complete: ${results.filter(r => r.success).length}/${users.length} successful`);
        return results;
    }

    // PATTERN 6: Error Propagation Chain - SHOULD BE DETECTED
    async errorPropagationChain(name, email) {
        console.log('\n=== CHAIN PATTERN 6: Error Propagation ===');

        try {
            // Step 1: HTTP call
            const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, {
                name,
                email
            });
            console.log('HTTP step: Success');

            // Step 2: Potentially failing gRPC call (simulated)
            try {
                // Simulate gRPC call that might fail
                if (Math.random() > 0.7) {
                    throw new Error('gRPC service unavailable');
                }
                console.log('gRPC step: Success');
            } catch (grpcError) {
                console.log('gRPC step failed, using Redis fallback');
                
                // Fallback to Redis
                await this.redisClient.hSet(`fallback:user:${httpResponse.data.id}`, {
                    id: httpResponse.data.id,
                    name: httpResponse.data.name,
                    email: httpResponse.data.email,
                    fallback: 'true'
                });
                console.log('Recovered using Redis fallback');
            }

            return httpResponse.data;
        } catch (error) {
            console.error('Chain failed at HTTP step:', error.message);
            throw error;
        }
    }

    // PATTERN 7: Context Propagation Chain - SHOULD BE DETECTED
    async contextPropagationChain(traceId, name, email) {
        console.log(`\n=== CHAIN PATTERN 7: Context Propagation (TraceID: ${traceId}) ===`);

        try {
            // HTTP call with trace context
            const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, {
                name,
                email
            }, {
                headers: {
                    'X-Trace-ID': traceId,
                    'X-User-Agent': 'test-orchestrator'
                }
            });
            console.log(`HTTP call completed with trace ID: ${traceId}`);

            // Kafka with trace context in headers
            await this.kafkaProducer.send({
                topic: 'user-events',
                messages: [{
                    value: JSON.stringify(httpResponse.data),
                    headers: {
                        'trace-id': traceId,
                        'timestamp': Date.now().toString()
                    }
                }]
            });
            console.log(`Kafka publish completed with trace ID: ${traceId}`);

            // Redis with trace context
            await this.redisClient.hSet(`traced:user:${httpResponse.data.id}`, {
                ...httpResponse.data,
                traceId
            });
            console.log(`Redis store completed with trace ID: ${traceId}`);

            return httpResponse.data;
        } catch (error) {
            console.error('Context propagation chain failed:', error.message);
            throw error;
        }
    }

    // PATTERN 8: Retry with Protocol Fallback - SHOULD BE DETECTED
    async retryWithProtocolFallback(name, email, maxRetries = 3) {
        console.log('\n=== CHAIN PATTERN 8: Retry with Protocol Fallback ===');

        const protocols = ['HTTP', 'Kafka', 'Redis', 'RabbitMQ'];

        for (let i = 0; i < maxRetries; i++) {
            const protocol = protocols[i % protocols.length];

            try {
                switch (protocol) {
                    case 'HTTP':
                        const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, {
                            name,
                            email
                        });
                        console.log(`Success using HTTP protocol`);
                        return httpResponse.data;

                    case 'Kafka':
                        await this.kafkaProducer.send({
                            topic: 'user-events',
                            messages: [{ value: JSON.stringify({ name, email }) }]
                        });
                        console.log(`Success using Kafka protocol`);
                        return { protocol: 'Kafka', name, email };

                    case 'Redis':
                        const userId = `redis-user-${Date.now()}`;
                        await this.redisClient.hSet(`user:${userId}`, { name, email });
                        console.log(`Success using Redis protocol`);
                        return { protocol: 'Redis', id: userId, name, email };

                    case 'RabbitMQ':
                        await this.rabbitmqChannel.assertQueue('user-queue');
                        this.rabbitmqChannel.sendToQueue('user-queue', 
                            Buffer.from(JSON.stringify({ name, email })));
                        console.log(`Success using RabbitMQ protocol`);
                        return { protocol: 'RabbitMQ', name, email };
                }
            } catch (error) {
                console.log(`Attempt ${i + 1} with ${protocol} failed: ${error.message}`);
            }
        }

        throw new Error('All retry attempts failed');
    }

    // PATTERN 9: Aggregate from Multiple Sources - SHOULD BE DETECTED
    async aggregateFromMultipleSources(userId) {
        console.log('\n=== CHAIN PATTERN 9: Aggregate from Multiple Sources ===');

        const results = await Promise.allSettled([
            // HTTP source
            axios.get(`${this.httpUserServiceUrl}/users/${userId}`)
                .then(res => ({ source: 'HTTP', data: res.data })),
            
            // Redis source
            this.redisClient.hGetAll(`user:${userId}`)
                .then(data => ({ source: 'Redis', data })),
            
            // Simulated gRPC source
            Promise.resolve({ source: 'gRPC', data: { id: userId, status: 'active' } })
        ]);

        const aggregated = {};
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                aggregated[result.value.source] = result.value.data;
            }
        });

        console.log(`Aggregated data from ${Object.keys(aggregated).length} sources`);
        return aggregated;
    }

    // PATTERN 10: Saga Pattern (Distributed Transaction) - SHOULD BE DETECTED
    async sagaPattern(name, email, amount) {
        console.log('\n=== CHAIN PATTERN 10: Saga Pattern (Distributed Transaction) ===');

        const executedSteps = [];

        const steps = [
            {
                name: 'CreateHTTPUser',
                execute: async () => {
                    const response = await axios.post(`${this.httpUserServiceUrl}/users`, {
                        name,
                        email
                    });
                    return response.data;
                },
                rollback: async (data) => {
                    console.log(`  Rolling back HTTP user creation for ${data.id}`);
                    await axios.delete(`${this.httpUserServiceUrl}/users/${data.id}`);
                }
            },
            {
                name: 'PublishToKafka',
                execute: async (userData) => {
                    await this.kafkaProducer.send({
                        topic: 'user-events',
                        messages: [{ value: JSON.stringify(userData) }]
                    });
                    return userData;
                },
                rollback: async (data) => {
                    console.log(`  Rolling back Kafka publish`);
                    // In reality, you'd publish a compensating event
                }
            },
            {
                name: 'StoreInRedis',
                execute: async (userData) => {
                    await this.redisClient.hSet(`saga:user:${userData.id}`, userData);
                    return userData;
                },
                rollback: async (data) => {
                    console.log(`  Rolling back Redis store`);
                    await this.redisClient.del(`saga:user:${data.id}`);
                }
            },
            {
                name: 'ProcessPayment',
                execute: async (userData) => {
                    const response = await axios.post(`${this.httpPaymentServiceUrl}/payments`, {
                        userId: userData.id,
                        amount
                    });
                    return response.data;
                },
                rollback: async (data) => {
                    console.log(`  Rolling back payment`);
                    // Refund logic would go here
                }
            }
        ];

        try {
            let stepData = null;

            for (let i = 0; i < steps.length; i++) {
                const step = steps[i];
                console.log(`Executing step ${i + 1}/${steps.length}: ${step.name}`);

                stepData = await step.execute(stepData);
                executedSteps.push({ step, data: stepData });
            }

            console.log('Saga completed successfully');
            return stepData;

        } catch (error) {
            console.error(`Saga failed at step ${executedSteps.length + 1}: ${error.message}`);

            // Rollback executed steps in reverse order
            for (let i = executedSteps.length - 1; i >= 0; i--) {
                const { step, data } = executedSteps[i];
                try {
                    await step.rollback(data);
                } catch (rollbackError) {
                    console.error(`  Rollback failed for ${step.name}: ${rollbackError.message}`);
                }
            }

            throw error;
        }
    }

    // PATTERN 11: Taint Flow - User Input to Privileged Operation - SHOULD BE DETECTED
    async taintFlowUserInputToPrivilegedOperation(userInput) {
        console.log('\n=== TAINT FLOW TEST: User Input → Services → Privileged Op ===');

        try {
            // Step 1: User input flows to HTTP service
            const httpResponse = await axios.post(`${this.httpUserServiceUrl}/users`, {
                name: userInput,
                email: `${userInput}@test.com`
            });

            // Step 2: HTTP response flows to Kafka
            await this.kafkaProducer.send({
                topic: 'user-events',
                messages: [{
                    value: JSON.stringify(httpResponse.data)
                }]
            });

            // Step 3: Data flows to Redis
            await this.redisClient.hSet(`taint:user:${httpResponse.data.id}`, {
                name: httpResponse.data.name
            });

            // Step 4: Execute privileged operation with tainted data
            return this.executePrivilegedOperation(httpResponse.data.name);

        } catch (error) {
            console.error('Taint flow failed:', error.message);
            throw error;
        }
    }

    // Privileged operation (sink for taint analysis)
    executePrivilegedOperation(data) {
        console.log(`PRIVILEGED OPERATION: Processing data: ${data}`);
        // This represents a security-sensitive operation
        return { status: 'executed', data };
    }

    // PATTERN 12: Serialize and Transmit - SHOULD BE DETECTED
    async serializeAndTransmit(data) {
        console.log('\n=== PATTERN 12: Serialize and Transmit ===');

        const serialized = JSON.stringify(data);

        // Transmit via multiple protocols
        await Promise.all([
            // HTTP
            axios.post(`${this.httpUserServiceUrl}/data`, { data: serialized }),
            
            // Kafka
            this.kafkaProducer.send({
                topic: 'data-events',
                messages: [{ value: serialized }]
            }),
            
            // Redis
            this.redisClient.set('transmitted:data', serialized, { EX: 300 }),
            
            // RabbitMQ
            this.rabbitmqChannel.assertQueue('data-queue').then(() => {
                this.rabbitmqChannel.sendToQueue('data-queue', Buffer.from(serialized));
            })
        ]);

        console.log('Data serialized and transmitted via all protocols');
    }

    async cleanup() {
        console.log('\nCleaning up orchestrator connections...');
        
        await this.kafkaProducer.disconnect();
        await this.redisClient.quit();
        await this.rabbitmqChannel.close();
        await this.rabbitmqConnection.close();
        
        console.log('Cleanup complete');
    }
}

// ========== TEST RUNNER ==========

async function runInterserviceChainTests() {
    console.log('Starting inter-service chain tests...\n');

    const orchestrator = new ChainedServiceOrchestrator();

    try {
        await orchestrator.initialize();

        // Test various chain patterns
        await orchestrator.httpToGrpcToKafkaChain('Alice', 'alice@test.com', 100);
        await orchestrator.grpcToRedisToRabbitMQChain('Bob', 'bob@test.com');
        await orchestrator.fanOutPattern('Charlie', 'charlie@test.com');
        await orchestrator.conditionalRouting('premium', 'David', 'david@test.com');
        
        await orchestrator.batchProcessingLoop([
            { name: 'User1', email: 'user1@test.com' },
            { name: 'User2', email: 'user2@test.com' },
            { name: 'User3', email: 'user3@test.com' }
        ]);

        await orchestrator.errorPropagationChain('Eve', 'eve@test.com');
        await orchestrator.contextPropagationChain('trace-123', 'Frank', 'frank@test.com');
        await orchestrator.retryWithProtocolFallback('Grace', 'grace@test.com', 3);
        
        // Test taint flow
        await orchestrator.taintFlowUserInputToPrivilegedOperation('TaintedInput');

        // Test saga
        await orchestrator.sagaPattern('Henry', 'henry@test.com', 299.99);

        console.log('\n=== Inter-Service Chain Test Summary ===');
        console.log('✓ HTTP → gRPC → Kafka chains');
        console.log('✓ gRPC → Redis → RabbitMQ chains');
        console.log('✓ Fan-out to multiple services');
        console.log('✓ Conditional protocol routing');
        console.log('✓ Batch processing loops');
        console.log('✓ Error propagation and recovery');
        console.log('✓ Context propagation across protocols');
        console.log('✓ Retry with protocol fallback');
        console.log('✓ Data aggregation from multiple sources');
        console.log('✓ Saga pattern (distributed transactions)');
        console.log('✓ Taint flow analysis patterns');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        await orchestrator.cleanup();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runInterserviceChainTests().catch(console.error);
}

module.exports = {
    ChainedServiceOrchestrator
};

/*
 * Expected Results:
 * ✅ 12 complex flows should be detected (patterns 1-12)
 * ❌ 0 flows should NOT be detected (all patterns involve external data)
 * 
 * Pattern Categories:
 * - Multi-Protocol Chains: HTTP → gRPC → Kafka, gRPC → Redis → RabbitMQ (patterns 1-2)
 * - Orchestration Patterns: Fan-out, Conditional routing, Batch processing (patterns 3-5)
 * - Resilience Patterns: Error propagation, Retry with fallback (patterns 6, 8)
 * - Cross-Cutting Concerns: Context propagation, Aggregation (patterns 7, 9)
 * - Transaction Patterns: Saga with rollback (pattern 10)
 * - Security Patterns: Taint flow analysis, Data serialization (patterns 11-12)
 * 
 * Complex Flow Chains to Detect:
 * 1. HTTP → gRPC → Kafka (3-hop chain)
 * 2. gRPC → Redis → RabbitMQ (3-hop chain)
 * 3. HTTP → Multiple services in parallel (fan-out)
 * 4. HTTP → gRPC → Kafka → Privileged operation (4-hop with sink)
 * 5. Conditional: Based on user type, route through different protocols
 * 6. Batch: Loop through users, HTTP → Kafka for each
 * 7. Error recovery: HTTP fails → Redis fallback
 * 8. Context: Trace ID propagated through HTTP → Kafka → Redis
 * 9. Retry: Try HTTP → Kafka → Redis → RabbitMQ in sequence
 * 10. Aggregation: Parallel HTTP + Redis + gRPC → Combined result
 * 11. Saga: Multi-step transaction with compensating rollback actions
 * 12. Serialization: JSON serialize → Send via HTTP, Kafka, Redis, RabbitMQ
 * 
 * Key Differences from test_interservice_flows.js:
 * - Focuses on COMPLEX MULTI-HOP chains vs simple direct flows
 * - Tests INTEGRATION between services vs individual sink detection
 * - Demonstrates REAL-WORLD patterns vs comprehensive sink catalog
 * - All patterns involve external data (no negative test cases)
 * - Tests orchestration logic, not just data transmission
 */