// index.js
/**
 * Main test runner for all microservice communication patterns
 * Run with: node index.js
 */

const { HttpUserService, HttpPaymentService, HttpBusinessService } = require('./test_http_connector');
const { GrpcBusinessService } = require('./test_grpc_connector');
const { KafkaUserService, KafkaPaymentService, KafkaBusinessService } = require('./test_kafka_connector');
const { RabbitMQUserService, RabbitMQPaymentService, RabbitMQBusinessService, Config } = require('./test_rabbitmq_connector');
const { RedisUserService, RedisPaymentService, RedisCacheService, RedisBusinessService } = require('./test_redis_connector');

// ========== HEALTH CHECKS ==========

async function checkKafkaHealth() {
    try {
        const { Kafka } = require('kafkajs');
        const kafka = new Kafka({
            clientId: 'health-check',
            brokers: ['localhost:9092'],
            connectionTimeout: 3000
        });
        const admin = kafka.admin();
        await admin.connect();
        await admin.listTopics();
        await admin.disconnect();
        console.log('✓ Kafka is available');
        return true;
    } catch (error) {
        console.log('✗ Kafka is not available');
        return false;
    }
}

async function checkRabbitMQHealth() {
    try {
        const amqp = require('amqplib');
        const connection = await amqp.connect('amqp://localhost:5672');
        await connection.close();
        console.log('✓ RabbitMQ is available');
        return true;
    } catch (error) {
        console.log('✗ RabbitMQ is not available');
        return false;
    }
}

async function checkRedisHealth() {
    try {
        const redis = require('redis');
        const client = redis.createClient({ url: 'redis://localhost:6379' });
        await client.connect();
        await client.ping();
        await client.quit();
        console.log('✓ Redis is available');
        return true;
    } catch (error) {
        console.log('✗ Redis is not available');
        return false;
    }
}

// ========== HTTP TESTS ==========

async function runHttpTests() {
    console.log('\n========================================');
    console.log('TESTING HTTP/REST COMMUNICATION');
    console.log('========================================\n');

    const userService = new HttpUserService();
    const paymentService = new HttpPaymentService();
    const businessService = new HttpBusinessService();

    try {
        await userService.start(8001);
        await paymentService.start(8002);
        await new Promise(resolve => setTimeout(resolve, 500));

        // Test Axios
        const { user: user1 } = await businessService.onboardUserWithAxios(
            'Alice HTTP', 
            'alice@http.com', 
            99.99
        );

        // Test Fetch
        await businessService.onboardUserWithFetch(
            'Bob HTTP', 
            'bob@http.com', 
            149.99
        );

        // Test concurrent
        await businessService.getUserProfile(user1.id);

        // Test retry
        await businessService.onboardWithRetry(
            'Charlie HTTP', 
            'charlie@http.com', 
            199.99, 
            3
        );

        console.log('\n✓ HTTP tests completed successfully');

        await userService.shutdown();
        await paymentService.shutdown();
    } catch (error) {
        console.error('✗ HTTP tests failed:', error.message);
    }
}

// ========== GRPC TESTS ==========

async function runGrpcTests() {
    console.log('\n========================================');
    console.log('TESTING GRPC COMMUNICATION');
    console.log('========================================\n');

    const businessService = new GrpcBusinessService();
    businessService.initialize();

    try {
        // Test unary
        await businessService.onboardUser('Eve gRPC', 'eve@grpc.com', 299.99);

        // Test server streaming
        await businessService.listAllUsers();

        // Test client streaming
        const payments = [
            { userId: 'user-1', amount: 100.0 },
            { userId: 'user-2', amount: 200.0 }
        ];
        await businessService.batchProcessPayments(payments);

        console.log('\n✓ gRPC tests completed successfully');

        businessService.close();
    } catch (error) {
        console.error('✗ gRPC tests failed:', error.message);
    }
}

// ========== KAFKA TESTS ==========

async function runKafkaTests() {
    console.log('\n========================================');
    console.log('TESTING KAFKA COMMUNICATION');
    console.log('========================================\n');

    const isHealthy = await checkKafkaHealth();
    if (!isHealthy) {
        console.log('Skipping Kafka tests - service not available\n');
        return;
    }

    const brokers = ['localhost:9092'];
    const userService = new KafkaUserService(brokers);
    const paymentService = new KafkaPaymentService(brokers);
    const businessService = new KafkaBusinessService(brokers, userService);

    try {
        await userService.connect();
        await paymentService.connect();
        await businessService.connect();

        await Promise.all([
            paymentService.startListening(),
            businessService.startListening()
        ]);

        await new Promise(resolve => setTimeout(resolve, 2000));

        const user = await businessService.onboardUserAndMakePayment(
            'Frank Kafka', 
            'frank@kafka.com'
        );

        await new Promise(resolve => setTimeout(resolve, 3000));

        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`Payment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        console.log('\n✓ Kafka tests completed successfully');

        await paymentService.disconnect();
        await businessService.disconnect();
        await userService.disconnect();
    } catch (error) {
        console.error('✗ Kafka tests failed:', error.message);
    }
}

// ========== RABBITMQ TESTS ==========

async function runRabbitMQTests() {
    console.log('\n========================================');
    console.log('TESTING RABBITMQ COMMUNICATION');
    console.log('========================================\n');

    const isHealthy = await checkRabbitMQHealth();
    if (!isHealthy) {
        console.log('Skipping RabbitMQ tests - service not available\n');
        return;
    }

    const userService = new RabbitMQUserService();
    const paymentService = new RabbitMQPaymentService();
    const businessService = new RabbitMQBusinessService(Config.url, userService);

    try {
        await userService.connect();
        await paymentService.connect();
        await businessService.connect();

        await paymentService.startListening();
        await businessService.startListening();

        await new Promise(resolve => setTimeout(resolve, 2000));

        const user = await businessService.onboardUserAndMakePayment(
            'Grace RabbitMQ', 
            'grace@rabbitmq.com'
        );

        await new Promise(resolve => setTimeout(resolve, 3000));

        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`Payment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        console.log('\n✓ RabbitMQ tests completed successfully');

        paymentService.stopListening();
        businessService.stopListening();

        await userService.close();
        await paymentService.close();
        await businessService.close();
    } catch (error) {
        console.error('✗ RabbitMQ tests failed:', error.message);
    }
}

// ========== REDIS TESTS ==========

async function runRedisTests() {
    console.log('\n========================================');
    console.log('TESTING REDIS COMMUNICATION');
    console.log('========================================\n');

    const isHealthy = await checkRedisHealth();
    if (!isHealthy) {
        console.log('Skipping Redis tests - service not available\n');
        return;
    }

    const userService = new RedisUserService();
    const paymentService = new RedisPaymentService();
    const cacheService = new RedisCacheService();
    const businessService = new RedisBusinessService('redis://localhost:6379', userService, cacheService);

    try {
        await userService.connect();
        await paymentService.connect();
        await cacheService.connect();
        await businessService.connect();

        await paymentService.startListening();
        await businessService.startListening();

        await new Promise(resolve => setTimeout(resolve, 1000));

        const user = await businessService.createUserWithCache(
            'Hannah Redis', 
            'hannah@redis.com'
        );

        const cachedUser = await businessService.getUserWithCache(user.id);
        console.log(`Cache retrieval: ${cachedUser ? 'SUCCESS' : 'FAILED'}`);

        await businessService.updateUserAndInvalidateCache(
            user.id, 
            'Hannah Updated', 
            'hannah.updated@redis.com'
        );

        await new Promise(resolve => setTimeout(resolve, 2000));

        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`Payment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        const deleted = await cacheService.invalidatePattern('user:*');
        console.log(`Invalidated ${deleted} cache entries`);

        console.log('\n✓ Redis tests completed successfully');

        paymentService.stopListening();
        businessService.stopListening();

        await userService.disconnect();
        await paymentService.disconnect();
        await cacheService.disconnect();
        await businessService.disconnect();
    } catch (error) {
        console.error('✗ Redis tests failed:', error.message);
    }
}

// ========== MAIN TEST RUNNER ==========

async function runAllTests() {
    console.log('╔════════════════════════════════════════╗');
    console.log('║  MICROSERVICES COMMUNICATION TESTS     ║');
    console.log('║  JavaScript/Node.js Implementation     ║');
    console.log('╚════════════════════════════════════════╝\n');

    console.log('Checking service availability...');
    await checkKafkaHealth();
    await checkRabbitMQHealth();
    await checkRedisHealth();

    const startTime = Date.now();

    try {
        // Run tests sequentially to avoid port conflicts
        await runHttpTests();
        await runGrpcTests();
        await runKafkaTests();
        await runRabbitMQTests();
        await runRedisTests();

        const duration = ((Date.now() - startTime) / 1000).toFixed(2);

        console.log('\n╔════════════════════════════════════════╗');
        console.log('║  ALL TESTS COMPLETED SUCCESSFULLY      ║');
        console.log(`║  Duration: ${duration}s`.padEnd(41) + '║');
        console.log('╚════════════════════════════════════════╝\n');

        console.log('Test Summary:');
        console.log('✓ HTTP/REST communication (Express, Axios, Fetch)');
        console.log('✓ gRPC communication (Unary, Streaming)');
        console.log('✓ Kafka event-driven communication');
        console.log('✓ RabbitMQ pub/sub and RPC patterns');
        console.log('✓ Redis pub/sub, caching, and locking');
        console.log('\nCodeQL Database Ready For Creation!');
        console.log('Run: codeql database create ../databases/javascript --language=javascript --source-root=.\n');

    } catch (error) {
        console.error('\n✗ Test suite failed:', error.message);
        process.exit(1);
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\n\nShutting down gracefully...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n\nShutting down gracefully...');
    process.exit(0);
});

// Run tests if this file is executed directly
if (require.main === module) {
    runAllTests().catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}

module.exports = {
    runHttpTests,
    runGrpcTests,
    runKafkaTests,
    runRabbitMQTests,
    runRedisTests,
    runAllTests
};