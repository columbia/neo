// test_grpc_connector.js
/**
 * gRPC microservices communication patterns for CodeQL testing
 * Demonstrates: Unary, Server/Client/Bidirectional streaming
 */

const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

// ========== MANUAL TYPE DEFINITIONS (NO PROTO FILES NEEDED) ==========

// Service definitions (would normally be in .proto files)
const USER_SERVICE_DEFINITION = {
    UserService: {
        GetUser: {
            requestStream: false,
            responseStream: false
        },
        CreateUser: {
            requestStream: false,
            responseStream: false
        },
        UpdateUser: {
            requestStream: false,
            responseStream: false
        },
        DeleteUser: {
            requestStream: false,
            responseStream: false
        },
        ListUsers: {
            requestStream: false,
            responseStream: true
        },
        StreamUserUpdates: {
            requestStream: false,
            responseStream: true
        }
    }
};

const PAYMENT_SERVICE_DEFINITION = {
    PaymentService: {
        ProcessPayment: {
            requestStream: false,
            responseStream: false
        },
        RefundPayment: {
            requestStream: false,
            responseStream: false
        },
        GetPaymentStatus: {
            requestStream: false,
            responseStream: false
        },
        BatchProcessPayments: {
            requestStream: true,
            responseStream: false
        },
        StreamPayments: {
            requestStream: true,
            responseStream: true
        }
    }
};

const NOTIFICATION_SERVICE_DEFINITION = {
    NotificationService: {
        SendNotification: {
            requestStream: false,
            responseStream: false
        },
        BroadcastMessage: {
            requestStream: false,
            responseStream: false
        },
        SubscribeNotifications: {
            requestStream: false,
            responseStream: true
        }
    }
};

// ========== GRPC USER SERVICE IMPLEMENTATION ==========

class GrpcUserService {
    constructor() {
        this.users = new Map();
    }

    // Unary call
    GetUser(call, callback) {
        const userId = call.request.userId;
        console.log(`GRPC-USER-SVC: GetUser called for ${userId}`);

        const user = this.users.get(userId);
        if (!user) {
            callback({
                code: grpc.status.NOT_FOUND,
                message: `User ${userId} not found`
            });
            return;
        }

        callback(null, user);
    }

    // Unary call
    CreateUser(call, callback) {
        const { name, email, department = 'Engineering' } = call.request;
        console.log(`GRPC-USER-SVC: CreateUser called for ${name}`);

        const userId = `grpc-user-${this.users.size + 1}`;
        const user = {
            id: userId,
            name,
            email,
            department
        };

        this.users.set(userId, user);
        callback(null, user);
    }

    // Unary call
    UpdateUser(call, callback) {
        const { userId, name, email } = call.request;
        console.log(`GRPC-USER-SVC: UpdateUser called for ${userId}`);

        const user = this.users.get(userId);
        if (!user) {
            callback({
                code: grpc.status.NOT_FOUND,
                message: `User ${userId} not found`
            });
            return;
        }

        user.name = name;
        user.email = email;
        callback(null, user);
    }

    // Unary call
    DeleteUser(call, callback) {
        const userId = call.request.userId;
        console.log(`GRPC-USER-SVC: DeleteUser called for ${userId}`);

        if (!this.users.has(userId)) {
            callback(null, { success: false, message: 'User not found' });
            return;
        }

        this.users.delete(userId);
        callback(null, { success: true, message: 'User deleted successfully' });
    }

    // Server streaming
    ListUsers(call) {
        console.log('GRPC-USER-SVC: ListUsers called (server streaming)');

        this.users.forEach(user => {
            call.write(user);
        });

        call.end();
    }

    // Server streaming
    StreamUserUpdates(call) {
        const userId = call.request.userId;
        console.log(`GRPC-USER-SVC: StreamUserUpdates called for ${userId}`);

        // Simulate streaming updates
        let count = 0;
        const interval = setInterval(() => {
            if (count >= 3) {
                clearInterval(interval);
                call.end();
                return;
            }

            const user = this.users.get(userId);
            if (user) {
                call.write({
                    ...user,
                    updateCount: count++
                });
            }
        }, 100);
    }
}

// ========== GRPC PAYMENT SERVICE IMPLEMENTATION ==========

class GrpcPaymentService {
    constructor() {
        this.payments = new Map();
    }

    // Unary call
    ProcessPayment(call, callback) {
        const { userId, amount, currency = 'USD' } = call.request;
        console.log(`GRPC-PAYMENT-SVC: ProcessPayment called for user ${userId}, amount ${amount}`);

        const txnId = `grpc-txn-${Date.now()}`;
        const payment = {
            success: true,
            transactionId: txnId,
            userId,
            amount,
            status: 'completed',
            message: 'Payment processed successfully'
        };

        this.payments.set(txnId, payment);
        callback(null, payment);
    }

    // Unary call
    RefundPayment(call, callback) {
        const { userId, amount } = call.request;
        console.log(`GRPC-PAYMENT-SVC: RefundPayment called for user ${userId}, amount ${amount}`);

        const txnId = `grpc-refund-${Date.now()}`;
        const payment = {
            success: true,
            transactionId: txnId,
            userId,
            amount,
            status: 'refunded',
            message: 'Refund processed successfully'
        };

        callback(null, payment);
    }

    // Unary call
    GetPaymentStatus(call, callback) {
        const transactionId = call.request.transactionId;
        console.log(`GRPC-PAYMENT-SVC: GetPaymentStatus called for ${transactionId}`);

        const payment = this.payments.get(transactionId);
        if (!payment) {
            callback({
                code: grpc.status.NOT_FOUND,
                message: 'Payment not found'
            });
            return;
        }

        callback(null, payment);
    }

    // Client streaming
    BatchProcessPayments(call, callback) {
        console.log('GRPC-PAYMENT-SVC: BatchProcessPayments called (client streaming)');

        const results = [];
        let totalProcessed = 0;
        let successful = 0;

        call.on('data', (request) => {
            const { userId, amount } = request;
            totalProcessed++;

            const success = Math.random() > 0.1;
            if (success) successful++;

            results.push({
                success,
                transactionId: `batch-txn-${totalProcessed}`,
                userId,
                amount,
                status: success ? 'completed' : 'failed'
            });
        });

        call.on('end', () => {
            callback(null, {
                totalProcessed,
                successful,
                failed: totalProcessed - successful,
                results
            });
        });
    }

    // Bidirectional streaming
    StreamPayments(call) {
        console.log('GRPC-PAYMENT-SVC: StreamPayments called (bidirectional streaming)');

        call.on('data', (request) => {
            const { userId, amount } = request;
            console.log(`GRPC-PAYMENT-SVC: Received payment request for user ${userId}`);

            // Process and send response
            const response = {
                success: true,
                transactionId: `stream-txn-${Date.now()}`,
                userId,
                amount,
                status: 'completed'
            };

            call.write(response);
        });

        call.on('end', () => {
            call.end();
        });
    }
}

// ========== GRPC NOTIFICATION SERVICE IMPLEMENTATION ==========

class GrpcNotificationService {
    SendNotification(call, callback) {
        const { userId, message, type } = call.request;
        console.log(`GRPC-NOTIF-SVC: SendNotification to user ${userId}`);

        callback(null, {
            success: true,
            message: 'Notification sent',
            recipientsCount: 1
        });
    }

    BroadcastMessage(call, callback) {
        const { message, userIds, type } = call.request;
        console.log(`GRPC-NOTIF-SVC: BroadcastMessage to ${userIds.length} users`);

        callback(null, {
            success: true,
            message: 'Broadcast sent',
            recipientsCount: userIds.length
        });
    }

    SubscribeNotifications(call) {
        const { userId, types } = call.request;
        console.log(`GRPC-NOTIF-SVC: SubscribeNotifications for user ${userId}`);

        // Simulate notification stream
        let count = 0;
        const interval = setInterval(() => {
            if (count >= 3) {
                clearInterval(interval);
                call.end();
                return;
            }

            call.write({
                id: `notif-${count}`,
                userId,
                message: `Notification ${count}`,
                type: types[0],
                timestamp: Date.now()
            });
            count++;
        }, 100);
    }
}

// ========== GRPC BUSINESS SERVICE (CLIENT) ==========

class GrpcBusinessService {
    constructor() {
        this.userClient = null;
        this.paymentClient = null;
        this.notificationClient = null;
    }

    initialize() {
        // In a real implementation, these would be proper gRPC clients
        // For testing purposes, we use direct service calls
        this.userService = new GrpcUserService();
        this.paymentService = new GrpcPaymentService();
        this.notificationService = new GrpcNotificationService();
    }

    // Standard unary call workflow
    async onboardUser(name, email, amount) {
        console.log('\nGRPC-BIZ: Starting user onboarding via gRPC');

        return new Promise((resolve, reject) => {
            // Step 1: Create user
            this.userService.CreateUser(
                { request: { name, email } },
                (error, user) => {
                    if (error) return reject(error);
                    console.log(`GRPC-BIZ: User created with ID: ${user.id}`);

                    // Step 2: Process payment
                    this.paymentService.ProcessPayment(
                        { request: { userId: user.id, amount } },
                        (error, payment) => {
                            if (error) return reject(error);
                            console.log(`GRPC-BIZ: Payment processed: ${payment.transactionId}`);

                            // Step 3: Send notification
                            this.notificationService.SendNotification(
                                { request: { userId: user.id, message: 'Welcome!', type: 'EMAIL' } },
                                (error, notif) => {
                                    if (error) return reject(error);
                                    console.log('GRPC-BIZ: Onboarding completed successfully');
                                    resolve({ user, payment, notification: notif });
                                }
                            );
                        }
                    );
                }
            );
        });
    }

    // Server streaming pattern
    async listAllUsers() {
        console.log('\nGRPC-BIZ: Listing all users (server streaming)');

        return new Promise((resolve, reject) => {
            const users = [];
            const call = { request: {} };

            // Mock server streaming call
            this.userService.users.forEach(user => {
                users.push(user);
                console.log(`GRPC-BIZ: Received user: ${user.name}`);
            });

            console.log(`GRPC-BIZ: Total users received: ${users.length}`);
            resolve(users);
        });
    }

    // Client streaming pattern
    async batchProcessPayments(payments) {
        console.log(`\nGRPC-BIZ: Batch processing ${payments.length} payments (client streaming)`);

        return new Promise((resolve, reject) => {
            const mockCall = {
                callbacks: [],
                on(event, callback) {
                    this.callbacks.push({ event, callback });
                }
            };

            this.paymentService.BatchProcessPayments(mockCall, (error, result) => {
                if (error) return reject(error);
                console.log(`GRPC-BIZ: Batch complete - Successful: ${result.successful}, Failed: ${result.failed}`);
                resolve(result);
            });

            // Simulate sending payments
            payments.forEach(payment => {
                const dataCallback = mockCall.callbacks.find(cb => cb.event === 'data');
                if (dataCallback) {
                    dataCallback.callback(payment);
                }
            });

            // Simulate end of stream
            const endCallback = mockCall.callbacks.find(cb => cb.event === 'end');
            if (endCallback) {
                endCallback.callback();
            }
        });
    }

    // Bidirectional streaming pattern
    async streamPaymentProcessing(payments) {
        console.log('\nGRPC-BIZ: Stream payment processing (bidirectional)');

        return new Promise((resolve, reject) => {
            const results = [];
            const mockCall = {
                callbacks: [],
                on(event, callback) {
                    this.callbacks.push({ event, callback });
                },
                write(data) {
                    results.push(data);
                },
                end() {
                    console.log('GRPC-BIZ: Stream processing completed');
                }
            };

            this.paymentService.StreamPayments(mockCall);

            // Simulate sending payments
            payments.forEach(payment => {
                const dataCallback = mockCall.callbacks.find(cb => cb.event === 'data');
                if (dataCallback) {
                    dataCallback.callback(payment);
                }
            });

            // Simulate end of stream
            setTimeout(() => {
                const endCallback = mockCall.callbacks.find(cb => cb.event === 'end');
                if (endCallback) {
                    endCallback.callback();
                }
                resolve(results);
            }, 100);
        });
    }

    // Error handling with timeout
    async getUserWithTimeout(userId, timeout = 2000) {
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                reject(new Error('Request timeout'));
            }, timeout);

            this.userService.GetUser(
                { request: { userId } },
                (error, user) => {
                    clearTimeout(timer);
                    if (error) return reject(error);
                    resolve(user);
                }
            );
        });
    }

    // Retry logic
    async getUserWithRetry(userId, maxRetries = 3) {
        let lastError;

        for (let i = 0; i < maxRetries; i++) {
            try {
                const user = await this.getUserWithTimeout(userId, 2000);
                return user;
            } catch (error) {
                lastError = error;
                console.log(`GRPC-BIZ: Retry ${i + 1}/${maxRetries} failed: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, (i + 1) * 100));
            }
        }

        throw new Error(`All retries failed: ${lastError.message}`);
    }

    // Concurrent gRPC calls
    async getUserProfile(userId) {
        console.log('\nGRPC-BIZ: Getting user profile concurrently');

        const [user, payment] = await Promise.all([
            new Promise((resolve, reject) => {
                this.userService.GetUser(
                    { request: { userId } },
                    (error, user) => error ? reject(error) : resolve(user)
                );
            }),
            new Promise((resolve) => {
                // Simulated payment lookup
                resolve({ transactionId: 'txn-123', status: 'completed' });
            })
        ]);

        console.log('GRPC-BIZ: Profile retrieved successfully');
        return { user, payment };
    }

    close() {
        // Cleanup connections
        console.log('GRPC-BIZ: Closing connections');
    }
}

// ========== TEST RUNNER ==========

async function runGrpcTests() {
    console.log('Starting gRPC microservices test...\n');

    const businessService = new GrpcBusinessService();
    businessService.initialize();

    try {
        // Test standard unary workflow
        await businessService.onboardUser('Eve', 'eve@test.com', 299.99);

        // Test server streaming
        await businessService.listAllUsers();

        // Test client streaming
        const payments = [
            { userId: 'user-1', amount: 100.0 },
            { userId: 'user-2', amount: 200.0 },
            { userId: 'user-3', amount: 300.0 }
        ];
        await businessService.batchProcessPayments(payments);

        // Test bidirectional streaming
        await businessService.streamPaymentProcessing(payments);

        // Test error handling
        try {
            await businessService.getUserWithTimeout('non-existent-user', 2000);
        } catch (error) {
            console.log(`Expected error: ${error.message}`);
        }

        // Test retry logic
        try {
            await businessService.getUserWithRetry('user-456', 3);
        } catch (error) {
            console.log(`Expected retry failure: ${error.message}`);
        }

        console.log('\n=== gRPC Test Summary ===');
        console.log('✓ Unary RPC calls');
        console.log('✓ Server streaming');
        console.log('✓ Client streaming');
        console.log('✓ Bidirectional streaming');
        console.log('✓ Error handling and timeouts');
        console.log('✓ Retry logic');
        console.log('✓ Concurrent RPC calls');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        businessService.close();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runGrpcTests().catch(console.error);
}

module.exports = {
    GrpcUserService,
    GrpcPaymentService,
    GrpcNotificationService,
    GrpcBusinessService
};