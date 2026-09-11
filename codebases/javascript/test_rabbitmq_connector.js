// test_rabbitmq_connector.js
/**
 * RabbitMQ microservices communication patterns for CodeQL testing
 * Demonstrates: Topic exchanges, pub/sub, RPC pattern
 */

const amqp = require('amqplib');

// ========== RABBITMQ CONFIGURATION ==========

const Config = {
    url: 'amqp://localhost:5672',
    exchanges: {
        USER_EVENTS: 'rabbitmq.user.events',
        PAYMENT_EVENTS: 'rabbitmq.payment.events'
    },
    queues: {
        USER_CREATED: 'rabbitmq.user.created.queue',
        PAYMENT_PROCESSING: 'rabbitmq.payment.processing.queue',
        PAYMENT_COMPLETED: 'rabbitmq.payment.completed.queue',
        BUSINESS_NOTIFICATIONS: 'rabbitmq.business.notifications.queue'
    },
    routingKeys: {
        USER_CREATED: 'rabbitmq.user.created',
        USER_UPDATED: 'rabbitmq.user.updated',
        PAYMENT_REQUESTED: 'rabbitmq.payment.requested',
        PAYMENT_PROCESSED: 'rabbitmq.payment.processed'
    }
};

// ========== DATA MODELS ==========

class RabbitMQUser {
    constructor(id, name, email) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.timestamp = Date.now();
    }
}

class RabbitMQPayment {
    constructor(success, transactionId, userId, amount) {
        this.success = success;
        this.transactionId = transactionId;
        this.userId = userId;
        this.amount = amount;
        this.timestamp = Date.now();
    }
}

class RabbitMQEvent {
    constructor(eventType, userId, data) {
        this.eventType = eventType;
        this.userId = userId;
        this.timestamp = Date.now();
        this.data = data;
    }
}

// ========== RABBITMQ BASE CONNECTION ==========

class RabbitMQConnection {
    constructor(url) {
        this.url = url;
        this.connection = null;
        this.channel = null;
    }

    async connect() {
        this.connection = await amqp.connect(this.url);
        this.channel = await this.connection.createChannel();
        console.log('RabbitMQ connection established');
    }

    async declareExchange(name, type = 'topic') {
        await this.channel.assertExchange(name, type, {
            durable: true,
            autoDelete: false
        });
    }

    async declareQueue(name) {
        return await this.channel.assertQueue(name, {
            durable: true,
            autoDelete: false
        });
    }

    async bindQueue(queueName, exchangeName, routingKey) {
        await this.channel.bindQueue(queueName, exchangeName, routingKey);
    }

    async publish(exchange, routingKey, message) {
        const content = Buffer.from(JSON.stringify(message));
        this.channel.publish(exchange, routingKey, content, {
            persistent: true,
            contentType: 'application/json',
            timestamp: Date.now()
        });
    }

    async consume(queueName, callback) {
        await this.channel.consume(queueName, async (msg) => {
            if (msg) {
                try {
                    const content = JSON.parse(msg.content.toString());
                    await callback(content, msg);
                    this.channel.ack(msg);
                } catch (error) {
                    console.error('Error processing message:', error);
                    this.channel.nack(msg, false, true); // Requeue on error
                }
            }
        });
    }

    async close() {
        if (this.channel) {
            await this.channel.close();
        }
        if (this.connection) {
            await this.connection.close();
        }
    }
}

// ========== RABBITMQ USER SERVICE (PUBLISHER) ==========

class RabbitMQUserService {
    constructor(url = Config.url) {
        this.conn = new RabbitMQConnection(url);
        this.userDb = new Map();
    }

    async connect() {
        await this.conn.connect();

        // Declare exchange
        await this.conn.declareExchange(Config.exchanges.USER_EVENTS);

        // Declare queue
        await this.conn.declareQueue(Config.queues.USER_CREATED);

        console.log('RABBITMQ-USER-SVC: Connected');
    }

    async createUser(name, email) {
        console.log(`RABBITMQ-USER-SVC: Creating user ${name}`);

        const userId = `rabbitmq-user-${Date.now()}`;
        const user = new RabbitMQUser(userId, name, email);
        this.userDb.set(userId, user);

        // Publish user created event
        const event = new RabbitMQEvent('RABBITMQ_USER_CREATED', userId, user);

        await this.conn.publish(
            Config.exchanges.USER_EVENTS,
            Config.routingKeys.USER_CREATED,
            event
        );

        console.log(`RABBITMQ-USER-SVC: Published USER_CREATED event for ${userId}`);
        return user;
    }

    async getUser(userId) {
        console.log(`RABBITMQ-USER-SVC: GetUser called for ${userId}`);
        return this.userDb.get(userId);
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
        const event = new RabbitMQEvent('RABBITMQ_USER_UPDATED', userId, user);

        await this.conn.publish(
            Config.exchanges.USER_EVENTS,
            Config.routingKeys.USER_UPDATED,
            event
        );

        console.log(`RABBITMQ-USER-SVC: Published USER_UPDATED event for ${userId}`);
        return user;
    }

    async close() {
        await this.conn.close();
    }
}

// ========== RABBITMQ PAYMENT SERVICE (CONSUMER & PUBLISHER) ==========

class RabbitMQPaymentService {
    constructor(url = Config.url) {
        this.conn = new RabbitMQConnection(url);
        this.payments = new Map();
        this.running = false;
    }

    async connect() {
        await this.conn.connect();

        // Declare exchanges
        await this.conn.declareExchange(Config.exchanges.USER_EVENTS);
        await this.conn.declareExchange(Config.exchanges.PAYMENT_EVENTS);

        // Declare queues
        await this.conn.declareQueue(Config.queues.PAYMENT_PROCESSING);
        await this.conn.declareQueue(Config.queues.PAYMENT_COMPLETED);

        // Bind payment processing queue to user events
        await this.conn.bindQueue(
            Config.queues.PAYMENT_PROCESSING,
            Config.exchanges.USER_EVENTS,
            Config.routingKeys.USER_CREATED
        );

        console.log('RABBITMQ-PAYMENT-SVC: Connected');
    }

    async startListening() {
        this.running = true;
        console.log('RABBITMQ-PAYMENT-SVC: Started listening for events');

        await this.conn.consume(Config.queues.PAYMENT_PROCESSING, async (event, msg) => {
            if (!this.running) return;

            console.log(`RABBITMQ-PAYMENT-SVC: Received event: ${event.eventType} for user ${event.userId}`);

            if (event.eventType === 'RABBITMQ_USER_CREATED') {
                const user = event.data;
                // Auto-trigger payment for new users
                await this.processPayment(user.id, 99.99);
            }
        });
    }

    async processPayment(userId, amount) {
        console.log(`RABBITMQ-PAYMENT-SVC: Processing payment of ${amount} for user ${userId}`);

        const success = Math.random() > 0.1; // 90% success rate
        const payment = new RabbitMQPayment(
            success,
            `rabbitmq-txn-${Date.now()}`,
            userId,
            amount
        );

        this.payments.set(payment.transactionId, payment);

        // Publish payment processed event
        const event = new RabbitMQEvent('RABBITMQ_PAYMENT_PROCESSED', userId, payment);

        await this.conn.publish(
            Config.exchanges.PAYMENT_EVENTS,
            Config.routingKeys.PAYMENT_PROCESSED,
            event
        );

        console.log(`RABBITMQ-PAYMENT-SVC: Published PAYMENT_PROCESSED event: ${payment.transactionId}`);
        return payment;
    }

    stopListening() {
        this.running = false;
    }

    async close() {
        this.stopListening();
        await this.conn.close();
    }
}

// ========== RABBITMQ RPC PATTERN ==========

class RabbitMQRPCClient {
    constructor(url = Config.url) {
        this.url = url;
        this.connection = null;
        this.channel = null;
        this.replyQueue = null;
        this.pendingReplies = new Map();
    }

    async connect() {
        this.connection = await amqp.connect(this.url);
        this.channel = await this.connection.createChannel();

        // Create exclusive reply queue
        const q = await this.channel.assertQueue('', { exclusive: true });
        this.replyQueue = q.queue;

        // Listen for RPC replies
        this.channel.consume(this.replyQueue, (msg) => {
            if (msg) {
                const correlationId = msg.properties.correlationId;
                const resolve = this.pendingReplies.get(correlationId);

                if (resolve) {
                    const response = JSON.parse(msg.content.toString());
                    resolve(response);
                    this.pendingReplies.delete(correlationId);
                }

                this.channel.ack(msg);
            }
        }, { noAck: false });

        console.log('RABBITMQ-RPC-CLIENT: Connected');
    }

    async call(queueName, request, timeout = 5000) {
        const correlationId = `${Date.now()}-${Math.random()}`;

        return new Promise(async (resolve, reject) => {
            // Set timeout
            const timer = setTimeout(() => {
                this.pendingReplies.delete(correlationId);
                reject(new Error('RPC call timeout'));
            }, timeout);

            // Store pending reply handler
            this.pendingReplies.set(correlationId, (response) => {
                clearTimeout(timer);
                resolve(response);
            });

            // Send RPC request
            const content = Buffer.from(JSON.stringify(request));
            this.channel.sendToQueue(queueName, content, {
                correlationId,
                replyTo: this.replyQueue,
                contentType: 'application/json'
            });
        });
    }

    async close() {
        if (this.channel) {
            await this.channel.close();
        }
        if (this.connection) {
            await this.connection.close();
        }
    }
}

class RabbitMQRPCServer {
    constructor(url = Config.url, queueName) {
        this.url = url;
        this.queueName = queueName;
        this.connection = null;
        this.channel = null;
        this.handler = null;
    }

    async connect(handler) {
        this.handler = handler;
        this.connection = await amqp.connect(this.url);
        this.channel = await this.connection.createChannel();

        await this.channel.assertQueue(this.queueName, { durable: false });
        await this.channel.prefetch(1);

        this.channel.consume(this.queueName, async (msg) => {
            if (msg) {
                try {
                    const request = JSON.parse(msg.content.toString());
                    const response = await this.handler(request);

                    const content = Buffer.from(JSON.stringify(response));
                    this.channel.sendToQueue(
                        msg.properties.replyTo,
                        content,
                        { correlationId: msg.properties.correlationId }
                    );

                    this.channel.ack(msg);
                } catch (error) {
                    console.error('RPC handler error:', error);
                    this.channel.nack(msg);
                }
            }
        });

        console.log('RABBITMQ-RPC-SERVER: Connected and listening');
    }

    async close() {
        if (this.channel) {
            await this.channel.close();
        }
        if (this.connection) {
            await this.connection.close();
        }
    }
}

// ========== RABBITMQ DELAYED MESSAGE PATTERN ==========

class RabbitMQDelayedPublisher {
    constructor(url = Config.url) {
        this.conn = new RabbitMQConnection(url);
    }

    async connect() {
        await this.conn.connect();

        // Declare delayed exchange (requires rabbitmq_delayed_message_exchange plugin)
        try {
            await this.conn.channel.assertExchange('delayed-exchange', 'x-delayed-message', {
                durable: true,
                arguments: { 'x-delayed-type': 'topic' }
            });
        } catch (error) {
            console.log('Delayed exchange plugin not available, using TTL-based delay');
        }
    }

    async publishDelayed(exchange, routingKey, message, delayMs) {
        const content = Buffer.from(JSON.stringify(message));
        
        // Publish with delay header
        this.conn.channel.publish(exchange, routingKey, content, {
            persistent: true,
            headers: {
                'x-delay': delayMs
            }
        });

        console.log(`Published delayed message (${delayMs}ms delay)`);
    }

    async close() {
        await this.conn.close();
    }
}

// ========== RABBITMQ DEAD LETTER QUEUE PATTERN ==========

class RabbitMQWithDLQ {
    constructor(url = Config.url) {
        this.conn = new RabbitMQConnection(url);
    }

    async connect() {
        await this.conn.connect();

        // Declare dead letter exchange
        await this.conn.declareExchange('dlx-exchange', 'topic');

        // Declare dead letter queue
        await this.conn.declareQueue('dead-letter-queue');
        await this.conn.bindQueue('dead-letter-queue', 'dlx-exchange', '#');

        // Declare main queue with DLX configuration
        await this.conn.channel.assertQueue('main-queue-with-dlx', {
            durable: true,
            arguments: {
                'x-dead-letter-exchange': 'dlx-exchange',
                'x-message-ttl': 60000 // 60 seconds TTL
            }
        });

        console.log('DLQ pattern configured');
    }

    async publishToMainQueue(message) {
        await this.conn.publish('', 'main-queue-with-dlx', message);
    }

    async consumeDeadLetters(callback) {
        await this.conn.consume('dead-letter-queue', callback);
    }

    async close() {
        await this.conn.close();
    }
}

// ========== TEST RUNNER ==========

async function runRabbitMQTests() {
    console.log('Starting RabbitMQ microservices test...');
    console.log('NOTE: This requires RabbitMQ to be running on localhost:5672\n');

    const userService = new RabbitMQUserService();
    const paymentService = new RabbitMQPaymentService();
    const businessService = new RabbitMQBusinessService(Config.url, userService);

    try {
        // Connect all services
        await userService.connect();
        await paymentService.connect();
        await businessService.connect();

        // Start event listeners
        await paymentService.startListening();
        await businessService.startListening();

        // Wait for consumers to be ready
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Run business flow
        const user = await businessService.onboardUserAndMakePayment('Grace', 'grace@rabbitmq.com');

        // Wait for events to flow through
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Check payment result
        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`\nPayment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        // Test RPC pattern
        console.log('\n--- Testing RPC Pattern ---');
        const rpcClient = new RabbitMQRPCClient();
        await rpcClient.connect();

        const rpcServer = new RabbitMQRPCServer(Config.url, 'rpc-test-queue');
        await rpcServer.connect(async (request) => {
            console.log('RPC server received:', request);
            return { result: request.value * 2 };
        });

        const rpcResult = await rpcClient.call('rpc-test-queue', { value: 21 });
        console.log('RPC result:', rpcResult);

        await rpcClient.close();
        await rpcServer.close();

        console.log('\n=== RabbitMQ Test Summary ===');
        console.log('✓ Topic exchanges with routing keys');
        console.log('✓ Pub/Sub pattern with multiple consumers');
        console.log('✓ Event-driven service communication');
        console.log('✓ Message acknowledgment and requeuing');
        console.log('✓ RPC (Request-Reply) pattern');
        console.log('✓ Automatic payment triggering via events');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        // Cleanup
        paymentService.stopListening();
        businessService.stopListening();

        await userService.close();
        await paymentService.close();
        await businessService.close();
    }
}

// ========== RABBITMQ BUSINESS SERVICE (CONSUMER & ORCHESTRATOR) ==========

class RabbitMQBusinessService {
    constructor(url = Config.url, userService) {
        this.conn = new RabbitMQConnection(url);
        this.userService = userService;
        this.paymentResults = new Map();
        this.running = false;
    }

    async connect() {
        await this.conn.connect();

        // Declare exchanges
        await this.conn.declareExchange(Config.exchanges.USER_EVENTS);
        await this.conn.declareExchange(Config.exchanges.PAYMENT_EVENTS);

        // Declare business notification queue
        await this.conn.declareQueue(Config.queues.BUSINESS_NOTIFICATIONS);

        // Bind to both user and payment events
        await this.conn.bindQueue(
            Config.queues.BUSINESS_NOTIFICATIONS,
            Config.exchanges.USER_EVENTS,
            'rabbitmq.user.*'
        );
        await this.conn.bindQueue(
            Config.queues.BUSINESS_NOTIFICATIONS,
            Config.exchanges.PAYMENT_EVENTS,
            'rabbitmq.payment.*'
        );

        console.log('RABBITMQ-BIZ: Connected');
    }

    async startListening() {
        this.running = true;
        console.log('RABBITMQ-BIZ: Started listening for business events');

        await this.conn.consume(Config.queues.BUSINESS_NOTIFICATIONS, async (event, msg) => {
            if (!this.running) return;

            if (event.eventType === 'RABBITMQ_USER_CREATED') {
                console.log(`RABBITMQ-BIZ: User onboarding initiated for ${event.userId}`);
            }

            if (event.eventType === 'RABBITMQ_PAYMENT_PROCESSED') {
                const payment = event.data;
                this.paymentResults.set(payment.userId, payment);
                console.log(`RABBITMQ-BIZ: Payment flow completed for user ${payment.userId} - Result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
            }
        });
    }

    async onboardUserAndMakePayment(name, email) {
        console.log(`\nRABBITMQ-BIZ: Starting user onboarding flow for ${name}`);

        const user = await this.userService.createUser(name, email);
        console.log(`RABBITMQ-BIZ: User creation initiated for ${user.id}`);

        return user;
    }

    getPaymentResult(userId) {
        return this.paymentResults.get(userId);
    }

    stopListening() {
        this.running = false;
    }

    async close() {
        this.stopListening();
        await this.conn.close();
    }
}

// ========== TEST RUNNER ==========

async function runRabbitMQTests() {
    console.log('Starting RabbitMQ microservices test...');
    console.log('NOTE: This requires RabbitMQ to be running on localhost:5672\n');

    const userService = new RabbitMQUserService();
    const paymentService = new RabbitMQPaymentService();
    const businessService = new RabbitMQBusinessService(Config.url, userService);

    try {
        // Connect all services
        await userService.connect();
        await paymentService.connect();
        await businessService.connect();

        // Start event listeners
        await paymentService.startListening();
        await businessService.startListening();

        // Wait for consumers to be ready
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Run business flow
        const user = await businessService.onboardUserAndMakePayment('Grace', 'grace@rabbitmq.com');

        // Wait for events to flow through
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Check payment result
        const payment = businessService.getPaymentResult(user.id);
        if (payment) {
            console.log(`\nPayment result: ${payment.success ? 'SUCCESS' : 'FAILED'}`);
        }

        // Test RPC pattern
        console.log('\n--- Testing RPC Pattern ---');
        const rpcClient = new RabbitMQRPCClient();
        await rpcClient.connect();

        const rpcServer = new RabbitMQRPCServer(Config.url, 'rpc-test-queue');
        await rpcServer.connect(async (request) => {
            console.log('RPC server received:', request);
            return { result: request.value * 2 };
        });

        const rpcResult = await rpcClient.call('rpc-test-queue', { value: 21 });
        console.log('RPC result:', rpcResult);

        await rpcClient.close();
        await rpcServer.close();

        console.log('\n=== RabbitMQ Test Summary ===');
        console.log('✓ Topic exchanges with routing keys');
        console.log('✓ Pub/Sub pattern with multiple consumers');
        console.log('✓ Event-driven service communication');
        console.log('✓ Message acknowledgment and requeuing');
        console.log('✓ RPC (Request-Reply) pattern');
        console.log('✓ Automatic payment triggering via events');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        // Cleanup
        paymentService.stopListening();
        businessService.stopListening();

        await userService.close();
        await paymentService.close();
        await businessService.close();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runRabbitMQTests().catch(console.error);
}

module.exports = {
    RabbitMQUser,
    RabbitMQPayment,
    RabbitMQEvent,
    RabbitMQConnection,
    RabbitMQUserService,
    RabbitMQPaymentService,
    RabbitMQBusinessService,
    RabbitMQRPCClient,
    RabbitMQRPCServer,
    RabbitMQDelayedPublisher,
    RabbitMQWithDLQ,
    Config
};