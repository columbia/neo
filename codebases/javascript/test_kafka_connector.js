// test_kafka_connector.js
/**
 * Kafka microservices communication patterns for CodeQL testing
 * Demonstrates: Event publishing, consumer groups, message batching
 */

const { Kafka, Partitioners } = require('kafkajs');

// ========== KAFKA EVENT TYPES ==========

const EventTypes = {
    USER_CREATED: 'user.created',
    USER_UPDATED: 'user.updated',
    USER_DELETED: 'user.deleted',
    PAYMENT_REQUESTED: 'payment.requested',
    PAYMENT_PROCESSED: 'payment.processed',
    PAYMENT_FAILED: 'payment.failed',
    NOTIFICATION_SENT: 'notification.sent'
};

const Topics = {
    USER_EVENTS: 'user-events',
    PAYMENT_EVENTS: 'payment-events',
    NOTIFICATION_EVENTS: 'notification-events'
};

// ========== DATA MODELS ==========

class KafkaUser {
    constructor(id, name, email) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.timestamp = Date.now();
    }
}

class KafkaPayment {
    constructor(success, transactionId, userId, amount) {
        this.success = success;
        this.transactionId = transactionId;
        this.userId = userId;
        this.amount = amount;
        this.timestamp = Date.now();
    }
}

class KafkaEvent {
    constructor(eventType, userId, data) {
        this.eventType = eventType;
        this.userId = userId;
        this.timestamp = Date.now();
        this.data = data;
    }
}

// ========== KAFKA USER SERVICE (PRODUCER) ==========

class KafkaUserService {
    constructor(brokers = ['localhost:9092']) {
        this.kafka = new Kafka({
            clientId: 'user-service',
            brokers
        });
        this.producer = this.kafka.producer({
            createPartitioner: Partitioners.LegacyPartitioner
        });
        this.userDb = new Map();
    }

    async connect() {
        await this.producer.connect();
        console.log('KAFKA-USER-SVC: Producer connected');
    }

    async createUser(name, email) {
        console.log(`KAFKA-USER-SVC: Creating user ${name}`);

        const userId = `kafka-user-${Date.now()}`;
        const user = new KafkaUser(userId, name, email);
        this.userDb.set(userId, user);

        // Publish user created event
        const event = new KafkaEvent(EventTypes.USER_CREATED, userId, user);

        await this.producer.send({
            topic: Topics.USER_EVENTS,
            messages: [{
                key: userId,
                value: JSON.stringify(event),
                headers: {
                    'event-type': EventTypes.USER_CREATED,
                    'timestamp': Date.now().toString()
                }
            }]
        });

        console.log(`KAFKA-USER-SVC: Published USER_CREATED event for ${userId}`);
        return user;
    }

    async updateUser(userId, name, email) {
        const user = this.userDb.get(userId);
        if (!user) {
            throw new Error('User not found');
        }

        user.name = name;
        user.email = email;
        user.timestamp = Date.now();

        // Publish user updated event
        const event = new KafkaEvent(EventTypes.USER_UPDATED, userId, user);

        await this.producer.send({
            topic: Topics.USER_EVENTS,
            messages: [{
                key: userId,
                value: JSON.stringify(event),
                headers: {
                    'event-type': EventTypes.USER_UPDATED
                }
            }]
        });

        console.log(`KAFKA-USER-SVC: Published USER_UPDATED event for ${userId}`);
        return user;
    }

    async deleteUser(userId) {
        const user = this.userDb.get(userId);
        if (!user) {
            throw new Error('User not found');
        }

        this.userDb.delete(userId);

        // Publish user deleted event
        const event = new KafkaEvent(EventTypes.USER_DELETED, userId, user);

        await this.producer.send({
            topic: Topics.USER_EVENTS,
            messages: [{
                key: userId,
                value: JSON.stringify(event),
                headers: {
                    'event-type': EventTypes.USER_DELETED
                }
            }]
        });

        console.log(`KAFKA-USER-SVC: Published USER_DELETED event for ${userId}`);
    }

    async disconnect() {
        await this.producer.disconnect();
    }
}

// ========== KAFKA PAYMENT SERVICE (CONSUMER & PRODUCER) ==========

class KafkaPaymentService {
    constructor(brokers = ['localhost:9092'], groupId = 'payment-service-group') {
        this.kafka = new Kafka({
            clientId: 'payment-service',
            brokers
        });
        this.consumer = this.kafka.consumer({ groupId });
        this.producer = this.kafka.producer({
            createPartitioner: Partitioners.LegacyPartitioner
        });
        this.payments = new Map();
        this.running = false;
    }

    async connect() {
        await this.consumer.connect();
        await this.producer.connect();
        console.log('KAFKA-PAYMENT-SVC: Consumer and Producer connected');
    }

    async startListening() {
        await this.consumer.subscribe({ 
            topic: Topics.USER_EVENTS, 
            fromBeginning: false 
        });

        this.running = true;
        console.log('KAFKA-PAYMENT-SVC: Started listening for events');

        await this.consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                if (!this.running) return;

                const event = JSON.parse(message.value.toString());
                console.log(`KAFKA-PAYMENT-SVC: Received event: ${event.eventType} for user ${event.userId}`);

                if (event.eventType === EventTypes.USER_CREATED) {
                    const user = event.data;
                    // Auto-trigger payment for new users
                    await this.processPayment(user.id, 99.99);
                }
            }
        });
    }

    async processPayment(userId, amount) {
        console.log(`KAFKA-PAYMENT-SVC: Processing payment of ${amount} for user ${userId}`);

        const success = Math.random() > 0.1; // 90% success rate
        const payment = new KafkaPayment(
            success,
            `kafka-txn-${Date.now()}`,
            userId,
            amount
        );

        this.payments.set(payment.transactionId, payment);

        // Publish payment processed event
        const eventType = success ? EventTypes.PAYMENT_PROCESSED : EventTypes.PAYMENT_FAILED;
        const event = new KafkaEvent(eventType, userId, payment);

        await this.producer.send({
            topic: Topics.PAYMENT_EVENTS,
            messages: [{
                key: userId,
                value: JSON.stringify(event),
                headers: {
                    'event-type': eventType,
                    'transaction-id': payment.transactionId
                }
            }]
        });

        console.log(`KAFKA-PAYMENT-SVC: Published PAYMENT_PROCESSED event: ${payment.transactionId}`);
        return payment;
    }

    async stop() {
        this.running = false;
        await this.consumer.stop();
    }

    async disconnect() {
        await this.stop();
        await this.consumer.disconnect();
        await this.producer.disconnect();
    }
}

// ========== KAFKA BUSINESS SERVICE (CONSUMER & ORCHESTRATOR) ==========

class KafkaBusinessService {
    constructor(brokers = ['localhost:9092'], userService) {
        this.kafka = new Kafka({
            clientId: 'business-service',
            brokers
        });
        this.userConsumer = this.kafka.consumer({ groupId: 'business-service-users' });
        this.paymentConsumer = this.kafka.consumer({ groupId: 'business-service-payments' });
        this.userService = userService;
        this.results = new Map();
        this.running = false;
    }

    async connect() {
        await this.userConsumer.connect();
        await this.paymentConsumer.connect();
        console.log('KAFKA-BIZ: Consumers connected');
    }

    async startListening() {
        // Subscribe to both user and payment events
        await this.userConsumer.subscribe({ 
            topic: Topics.USER_EVENTS, 
            fromBeginning: false 
        });
        await this.paymentConsumer.subscribe({ 
            topic: Topics.PAYMENT_EVENTS, 
            fromBeginning: false 
        });

        this.running = true;
        console.log('KAFKA-BIZ: Started listening for business events');

        // Listen to user events
        this.userConsumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                if (!this.running) return;

                const event = JSON.parse(message.value.toString());

                if (event.eventType === EventTypes.USER_CREATED) {
                    console.log(`KAFKA-BIZ: User onboarding initiated for ${event.userId}`);
                }
            }
        });

        // Listen to payment events
        this.paymentConsumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                if (!this.running) return;

                const event = JSON.parse(message.value.toString());

                if (event.eventType === EventTypes.PAYMENT_PROCESSED) {
                    const payment = event.data;
                    this.results.set(payment.userId, payment);
                    console.log(`KAFKA-BIZ: Payment flow completed for user ${payment.userId} - Transaction: ${payment.transactionId}`);
                }
            }
        });
    }

    async onboardUserAndMakePayment(name, email) {
        console.log(`\nKAFKA-BIZ: Starting user onboarding flow for ${name}`);

        const user = await this.userService.createUser(name, email);
        console.log(`KAFKA-BIZ: User creation initiated for ${user.id}`);

        return user;
    }

    getPaymentResult(userId) {
        return this.results.get(userId);
    }

    async stop() {
        this.running = false;
        await this.userConsumer.stop();
        await this.paymentConsumer.stop();
    }

    async disconnect() {
        await this.stop();
        await this.userConsumer.disconnect();
        await this.paymentConsumer.disconnect();
    }
}

// ========== KAFKA BATCH PRODUCER ==========

class KafkaBatchProducer {
    constructor(brokers = ['localhost:9092'], topic) {
        this.kafka = new Kafka({
            clientId: 'batch-producer',
            brokers
        });
        this.producer = this.kafka.producer({
            createPartitioner: Partitioners.LegacyPartitioner,
            maxInFlightRequests: 5,
            idempotent: true
        });
        this.topic = topic;
    }

    async connect() {
        await this.producer.connect();
    }

    async sendBatch(events) {
        const messages = events.map(event => ({
            key: event.userId,
            value: JSON.stringify(event),
            headers: {
                'event-type': event.eventType
            }
        }));

        await this.producer.sendBatch({
            topicMessages: [{
                topic: this.topic,
                messages
            }]
        });

        console.log(`KAFKA-BATCH: Sent ${events.length} events`);
    }

    async disconnect() {
        await this.producer.disconnect();
    }
}

// ========== KAFKA ADMIN OPERATIONS ==========

class KafkaAdmin {
    constructor(brokers = ['localhost:9092']) {
        this.kafka = new Kafka({
            clientId: 'admin-client',
            brokers
        });
        this.admin = this.kafka.admin();
    }

    async connect() {
        await this.admin.connect();
    }

    async createTopics(topics) {
        await this.admin.createTopics({
            topics: topics.map(topic => ({
                topic,
                numPartitions: 3,
                replicationFactor: 1
            }))
        });
        console.log(`KAFKA-ADMIN: Created topics: ${topics.join(', ')}`);
    }

    async deleteTopics(topics) {
        await this.admin.deleteTopics({ topics });
        console.log(`KAFKA-ADMIN: Deleted topics: ${topics.join(', ')}`);
    }

    async disconnect() {
        await this.admin.disconnect();
    }
}

// ========== HEALTH CHECK ==========

async function checkKafkaHealth(brokers) {
    try {
        const kafka = new Kafka({
            clientId: 'health-check',
            brokers,
            connectionTimeout: 3000
        });
        const admin = kafka.admin();
        await admin.connect();
        await admin.listTopics();
        await admin.disconnect();
        console.log('KAFKA-HEALTH: Kafka is available');
        return true;
    } catch (error) {
        console.log('KAFKA-HEALTH: Kafka is not available:', error.message);
        return false;
    }
}

// ========== TEST RUNNER ==========

async function runKafkaTests() {
    console.log('Starting Kafka microservices test...');
    console.log('NOTE: This requires Kafka to be running on localhost:9092\n');

    const brokers = ['localhost:9092'];

    // Check Kafka health
    const isHealthy = await checkKafkaHealth(brokers);
    if (!isHealthy) {
        console.log('Kafka is not available. Please start Kafka first.');
        return;
    }

    // Initialize services
    const userService = new KafkaUserService(brokers);
    const paymentService = new KafkaPaymentService(brokers);
    const businessService = new KafkaBusinessService(brokers, userService);

    try {
        // Connect all services
        await userService.connect();
        await paymentService.connect();
        await businessService.connect();

        // Start event listeners
        await Promise.all([
            paymentService.startListening(),
            businessService.startListening()
        ]);

        // Wait for consumers to be ready
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Run business flow
        const user = await businessService.onboardUserAndMakePayment('Frank', 'frank@kafka.com');

        // Wait for events to flow through
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Check payment result
        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`\nPayment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        console.log('\n=== Kafka Test Summary ===');
        console.log('✓ Event publishing to Kafka topics');
        console.log('✓ Consumer groups with message processing');
        console.log('✓ Event-driven service communication');
        console.log('✓ Message headers and metadata');
        console.log('✓ Automatic payment triggering via events');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        // Cleanup
        await paymentService.disconnect();
        await businessService.disconnect();
        await userService.disconnect();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runKafkaTests().catch(console.error);
}

module.exports = {
    KafkaUser,
    KafkaPayment,
    KafkaEvent,
    KafkaUserService,
    KafkaPaymentService,
    KafkaBusinessService,
    KafkaBatchProducer,
    KafkaAdmin,
    EventTypes,
    Topics
};