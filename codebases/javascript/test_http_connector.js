// test_http_connector.js
/**
 * HTTP/REST microservices communication patterns for CodeQL testing
 * Demonstrates: Express, Axios, Fetch, Request/Response flows
 */

const express = require('express');
const axios = require('axios');
const fetch = require('node-fetch');

// ========== DATA MODELS ==========

class User {
    constructor(id, name, email) {
        this.id = id;
        this.name = name;
        this.email = email;
    }
}

class Payment {
    constructor(success, transactionId, userId, amount) {
        this.success = success;
        this.transactionId = transactionId;
        this.userId = userId;
        this.amount = amount;
    }
}

// ========== HTTP USER SERVICE ==========

class HttpUserService {
    constructor() {
        this.userDb = new Map();
        this.app = express();
        this.setupRoutes();
    }

    setupRoutes() {
        this.app.use(express.json());

        // GET user by ID
        this.app.get('/users/:userId', (req, res) => {
            const userId = req.params.userId;
            console.log(`HTTP-USER-SVC: GetUser called for ${userId}`);
            
            const user = this.userDb.get(userId);
            if (!user) {
                return res.status(404).json({ error: 'User not found' });
            }
            
            res.json(user);
        });

        // CREATE user
        this.app.post('/users', (req, res) => {
            const { name, email } = req.body;
            console.log(`HTTP-USER-SVC: CreateUser called for ${name}`);
            
            const userId = `http-user-${this.userDb.size + 1}`;
            const user = new User(userId, name, email);
            this.userDb.set(userId, user);
            
            res.status(201).json(user);
        });

        // UPDATE user
        this.app.put('/users/:userId', (req, res) => {
            const userId = req.params.userId;
            const { name, email } = req.body;
            
            const user = this.userDb.get(userId);
            if (!user) {
                return res.status(404).json({ error: 'User not found' });
            }
            
            user.name = name;
            user.email = email;
            res.json(user);
        });

        // DELETE user
        this.app.delete('/users/:userId', (req, res) => {
            const userId = req.params.userId;
            
            if (!this.userDb.has(userId)) {
                return res.status(404).json({ error: 'User not found' });
            }
            
            this.userDb.delete(userId);
            res.json({ message: 'User deleted' });
        });
    }

    start(port) {
        return new Promise((resolve) => {
            this.server = this.app.listen(port, () => {
                console.log(`HTTP-USER-SVC: Started on port ${port}`);
                resolve();
            });
        });
    }

    shutdown() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(resolve);
            } else {
                resolve();
            }
        });
    }
}

// ========== HTTP PAYMENT SERVICE ==========

class HttpPaymentService {
    constructor() {
        this.app = express();
        this.setupRoutes();
    }

    setupRoutes() {
        this.app.use(express.json());

        // PROCESS payment
        this.app.post('/payments', (req, res) => {
            const { userId, amount } = req.body;
            console.log(`HTTP-PAYMENT-SVC: ProcessPayment called for user ${userId}, amount ${amount}`);
            
            const success = Math.random() > 0.1; // 90% success rate
            const payment = new Payment(
                success,
                `http-txn-${Math.floor(Math.random() * 9000) + 1000}`,
                userId,
                amount
            );
            
            res.status(201).json(payment);
        });

        // REFUND payment
        this.app.post('/payments/refund', (req, res) => {
            const { userId, amount } = req.body;
            console.log(`HTTP-PAYMENT-SVC: RefundPayment called for user ${userId}, amount ${amount}`);
            
            const payment = new Payment(
                true,
                `http-refund-${Math.floor(Math.random() * 9000) + 1000}`,
                userId,
                amount
            );
            
            res.json(payment);
        });
    }

    start(port) {
        return new Promise((resolve) => {
            this.server = this.app.listen(port, () => {
                console.log(`HTTP-PAYMENT-SVC: Started on port ${port}`);
                resolve();
            });
        });
    }

    shutdown() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(resolve);
            } else {
                resolve();
            }
        });
    }
}

// ========== HTTP BUSINESS SERVICE (CLIENT) ==========

class HttpBusinessService {
    constructor(userServiceUrl = 'http://localhost:8001', paymentServiceUrl = 'http://localhost:8002') {
        this.userServiceUrl = userServiceUrl;
        this.paymentServiceUrl = paymentServiceUrl;
    }

    // Sequential HTTP calls using Axios
    async onboardUserWithAxios(name, email, amount) {
        console.log(`\nHTTP-BIZ (Axios): Starting user onboarding for ${name}`);

        try {
            // Step 1: Create user
            const userResponse = await axios.post(`${this.userServiceUrl}/users`, {
                name,
                email
            });
            const user = userResponse.data;
            console.log(`HTTP-BIZ (Axios): User created with ID: ${user.id}`);

            // Step 2: Process payment
            const paymentResponse = await axios.post(`${this.paymentServiceUrl}/payments`, {
                userId: user.id,
                amount
            });
            const payment = paymentResponse.data;
            console.log(`HTTP-BIZ (Axios): Payment processed: ${payment.transactionId}`);

            return { user, payment };
        } catch (error) {
            console.error(`HTTP-BIZ (Axios): Error: ${error.message}`);
            throw error;
        }
    }

    // Sequential HTTP calls using Fetch
    async onboardUserWithFetch(name, email, amount) {
        console.log(`\nHTTP-BIZ (Fetch): Starting user onboarding for ${name}`);

        try {
            // Step 1: Create user
            const userResponse = await fetch(`${this.userServiceUrl}/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });

            if (!userResponse.ok) {
                throw new Error(`User creation failed: ${userResponse.status}`);
            }

            const user = await userResponse.json();
            console.log(`HTTP-BIZ (Fetch): User created with ID: ${user.id}`);

            // Step 2: Process payment
            const paymentResponse = await fetch(`${this.paymentServiceUrl}/payments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: user.id, amount })
            });

            if (!paymentResponse.ok) {
                throw new Error(`Payment failed: ${paymentResponse.status}`);
            }

            const payment = await paymentResponse.json();
            console.log(`HTTP-BIZ (Fetch): Payment processed: ${payment.transactionId}`);

            return { user, payment };
        } catch (error) {
            console.error(`HTTP-BIZ (Fetch): Error: ${error.message}`);
            throw error;
        }
    }

    // Concurrent HTTP calls using Promise.all
    async getUserProfile(userId) {
        console.log(`\nHTTP-BIZ: Getting full profile for user ${userId} (concurrent)`);

        try {
            const [userResponse, paymentsData] = await Promise.all([
                axios.get(`${this.userServiceUrl}/users/${userId}`),
                // Simulated payments endpoint
                Promise.resolve([{
                    success: true,
                    transactionId: 'txn-001',
                    userId: userId,
                    amount: 99.99
                }])
            ]);

            console.log('HTTP-BIZ: Profile retrieved successfully');
            return {
                user: userResponse.data,
                payments: paymentsData
            };
        } catch (error) {
            console.error(`HTTP-BIZ: Error: ${error.message}`);
            throw error;
        }
    }

    // Error handling pattern with retry
    async onboardWithRetry(name, email, amount, maxRetries = 3) {
        let lastError;

        for (let i = 0; i < maxRetries; i++) {
            try {
                return await this.onboardUserWithAxios(name, email, amount);
            } catch (error) {
                lastError = error;
                console.log(`HTTP-BIZ: Retry ${i + 1}/${maxRetries} failed: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, (i + 1) * 100));
            }
        }

        throw new Error(`All retries failed: ${lastError.message}`);
    }

    // Chained HTTP calls
    async chainedOperations(name, email) {
        console.log('\nHTTP-BIZ: Starting chained operations');

        try {
            // Create user
            const { user } = await this.onboardUserWithAxios(name, email, 100.0);

            // Update user
            await axios.put(`${this.userServiceUrl}/users/${user.id}`, {
                name: `${user.name} Updated`,
                email: `updated-${user.email}`
            });
            console.log('HTTP-BIZ: User updated');

            // Process refund
            await axios.post(`${this.paymentServiceUrl}/payments/refund`, {
                userId: user.id,
                amount: 50.0
            });
            console.log('HTTP-BIZ: Refund processed');
        } catch (error) {
            console.error(`HTTP-BIZ: Error in chained operations: ${error.message}`);
            throw error;
        }
    }

    // Multiple outbound calls (fan-out pattern)
    async broadcastToMultipleServices(userId) {
        console.log('\nHTTP-BIZ: Broadcasting to multiple services');

        const services = [
            axios.get(`${this.userServiceUrl}/users/${userId}`),
            axios.post(`${this.paymentServiceUrl}/payments`, {
                userId,
                amount: 0
            })
        ];

        try {
            await Promise.all(services);
            console.log('HTTP-BIZ: Broadcast completed');
        } catch (error) {
            console.error(`HTTP-BIZ: Error in broadcast: ${error.message}`);
            throw error;
        }
    }

    // Request with timeout
    async getUserWithTimeout(userId, timeout = 2000) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(`${this.userServiceUrl}/users/${userId}`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }
}

// ========== TEST RUNNER ==========

async function runHttpTests() {
    console.log('Starting HTTP microservices test...\n');

    const userService = new HttpUserService();
    const paymentService = new HttpPaymentService();
    const businessService = new HttpBusinessService();

    try {
        // Start services
        await userService.start(8001);
        await paymentService.start(8002);

        // Wait for services to be ready
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Test Axios flow
        const { user: user1 } = await businessService.onboardUserWithAxios('Alice', 'alice@test.com', 99.99);

        // Test Fetch flow
        await businessService.onboardUserWithFetch('Bob', 'bob@test.com', 149.99);

        // Test concurrent operations
        await businessService.getUserProfile(user1.id);

        // Test retry logic
        await businessService.onboardWithRetry('Charlie', 'charlie@test.com', 199.99, 3);

        // Test chained operations
        await businessService.chainedOperations('David', 'david@test.com');

        // Test broadcast
        await businessService.broadcastToMultipleServices(user1.id);

        console.log('\n=== HTTP Test Summary ===');
        console.log('✓ Sequential HTTP calls (Axios & Fetch)');
        console.log('✓ Concurrent HTTP operations');
        console.log('✓ Error handling and retry logic');
        console.log('✓ Chained service calls');
        console.log('✓ Fan-out broadcast pattern');

    } catch (error) {
        console.error('Test error:', error);
    } finally {
        // Cleanup
        await userService.shutdown();
        await paymentService.shutdown();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runHttpTests().catch(console.error);
}

module.exports = {
    User,
    Payment,
    HttpUserService,
    HttpPaymentService,
    HttpBusinessService
};