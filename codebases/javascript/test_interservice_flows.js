// test_interservice_flows.js
/**
 * Single file test for JavaScript inter-service taint flow validation.
 * Run your CodeQL query on this file to validate outbound data transmission models.
 */

const express = require('express');
const axios = require('axios');
const fetch = require('node-fetch');
const { Kafka } = require('kafkajs');
const amqp = require('amqplib');
const redis = require('redis');

const app = express();
app.use(express.json());

// Initialize clients
const kafka = new Kafka({ clientId: 'test-client', brokers: ['localhost:9092'] });
const kafkaProducer = kafka.producer();
const redisClient = redis.createClient({ url: 'redis://localhost:6379' });

// Mock gRPC stub
class UserServiceStub {
    GetUser(request) {
        return { id: request.userId, name: 'test', role: 'user' };
    }
    
    ProcessData(request) {
        return { id: '1', name: 'processed', role: request.data };
    }
}

const userGrpcStub = new UserServiceStub();

// TEST 1: HTTP Client with Axios - SHOULD BE DETECTED
app.post('/test-http-axios', async (req, res) => {
    const userInput = req.body.userInput;
    const response = await axios.get(`https://api.example.com/${userInput}`);
    return res.json(executePrivilegedOperation(response.data));
});

// TEST 2: HTTP Client with Fetch - SHOULD BE DETECTED
app.post('/test-http-fetch', async (req, res) => {
    const userInput = req.body.userInput;
    const response = await fetch(`https://api.example.com/${userInput}`);
    const data = await response.text();
    return res.json(executePrivilegedOperation(data));
});

// TEST 3: HTTP POST with JSON Body - SHOULD BE DETECTED
app.post('/test-http-json', async (req, res) => {
    const userRequest = req.body;
    const payload = { query: userRequest.name, email: userRequest.email };
    const response = await axios.post('https://api.example.com/users', payload);
    return res.json(executePrivilegedOperation(response.data.data));
});

// TEST 4: HTTPX Style Request - SHOULD BE DETECTED
app.post('/test-httpx', async (req, res) => {
    const userInput = req.body.userInput;
    const response = await fetch('https://api.example.com/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: userInput })
    });
    const result = await response.text();
    return res.json(executePrivilegedOperation(result));
});

// TEST 5: gRPC Service Call - SHOULD BE DETECTED
app.post('/test-grpc', async (req, res) => {
    const userId = req.body.userId;
    const user = userGrpcStub.GetUser({ userId });
    return res.json(executePrivilegedOperation(user.role));
});

// TEST 6: Kafka Producer - SHOULD BE DETECTED
app.post('/test-kafka', async (req, res) => {
    const message = req.body.message;
    await kafkaProducer.send({
        topic: 'user-events',
        messages: [{ value: message }]
    });
    return res.json({ status: 'Message sent to Kafka' });
});

// TEST 7: RabbitMQ Publisher - SHOULD BE DETECTED
app.post('/test-rabbitmq', async (req, res) => {
    const message = req.body.message;
    const connection = await amqp.connect('amqp://localhost:5672');
    const channel = await connection.createChannel();
    await channel.assertQueue('user-queue');
    channel.sendToQueue('user-queue', Buffer.from(message));
    await channel.close();
    await connection.close();
    return res.json({ status: 'Message sent to RabbitMQ' });
});

// TEST 8: Redis Operations - SHOULD BE DETECTED
app.post('/test-redis', async (req, res) => {
    const userData = req.body.userData;
    await redisClient.connect();
    await redisClient.set('user_data', userData);
    await redisClient.publish('user-channel', userData);
    await redisClient.quit();
    return res.json({ status: 'Data stored and published to Redis' });
});

// TEST 9: GraphQL Query via HTTP - SHOULD BE DETECTED
app.post('/test-graphql', async (req, res) => {
    const userId = req.body.userId;
    const query = { query: `{ user(id: "${userId}") { role } }` };
    const response = await axios.post('https://api.example.com/graphql', query);
    return res.json(executePrivilegedOperation(response.data.data.user.role));
});

// TEST 10: WebSocket Simulation - SHOULD BE DETECTED
app.post('/test-websocket', async (req, res) => {
    const message = req.body.message;
    const websocketPayload = { type: 'message', data: message };
    const response = await axios.post('https://ws.example.com/send', websocketPayload);
    return res.json(executePrivilegedOperation(response.data));
});

// TEST 11: Chained Inter-Service Calls - SHOULD BE DETECTED
app.post('/test-chain', async (req, res) => {
    const userInput = req.body.userInput;
    
    // Step 1: HTTP call
    const httpResponse = await axios.get(`https://api.example.com/${userInput}`);
    
    // Step 2: gRPC call with HTTP response data
    const user = userGrpcStub.ProcessData({ data: httpResponse.data });
    
    // Step 3: Kafka publish with gRPC result
    await kafkaProducer.send({
        topic: 'processed-users',
        messages: [{ value: user.role }]
    });
    
    return res.json(executePrivilegedOperation(user.role));
});

// TEST 12: Multiple Outbound Calls - SHOULD BE DETECTED
app.post('/test-multiple', async (req, res) => {
    const userData = req.body.userData;
    
    // Send to multiple services
    await Promise.all([
        axios.post('https://service1.example.com/users', { data: userData }),
        kafkaProducer.send({ topic: 'user-topic', messages: [{ value: userData }] }),
        redisClient.connect().then(() => redisClient.set(`user:${userData}`, 'processed'))
    ]);
    
    return res.json({ status: 'Data sent to multiple services' });
});

// TEST 13: REST Template Style (Spring Boot equivalent) - SHOULD BE DETECTED
app.post('/test-resttemplate', async (req, res) => {
    const userInput = req.body.userInput;
    // Simulating RestTemplate behavior with axios
    const response = await axios({
        method: 'get',
        url: 'https://api.example.com/users',
        params: { query: userInput }
    });
    return res.json(executePrivilegedOperation(response.data));
});

// TEST 14: Event-Driven Flow - SHOULD BE DETECTED
app.post('/test-event', async (req, res) => {
    const eventData = req.body;
    
    // Publish event to Kafka
    await kafkaProducer.send({
        topic: 'events',
        messages: [{
            key: eventData.userId,
            value: JSON.stringify(eventData),
            headers: { 'event-type': 'USER_ACTION' }
        }]
    });
    
    return res.json({ status: 'Event published' });
});

// TEST 15: Database Query Simulation - SHOULD BE DETECTED
app.post('/test-database', async (req, res) => {
    const userQuery = req.body.userQuery;
    // Simulating database query via HTTP API
    const queryPayload = { sql: `SELECT * FROM users WHERE name = '${userQuery}'` };
    const response = await axios.post('https://db.example.com/query', queryPayload);
    return res.json(executePrivilegedOperation(response.data.result));
});

// TEST 16: Async/Await Pattern - SHOULD BE DETECTED
app.post('/test-async', async (req, res) => {
    const input = req.body.input;
    
    const fetchData = async () => {
        const response = await fetch(`https://api.example.com/${input}`);
        return await response.json();
    };
    
    const data = await fetchData();
    return res.json(executePrivilegedOperation(data));
});

// TEST 17: Promise Chain Pattern - SHOULD BE DETECTED
app.post('/test-promise-chain', (req, res) => {
    const userInput = req.body.userInput;
    
    axios.get(`https://api.example.com/${userInput}`)
        .then(response => {
            return executePrivilegedOperation(response.data);
        })
        .then(result => {
            res.json(result);
        })
        .catch(error => {
            res.status(500).json({ error: error.message });
        });
});

// TEST 18: Callback Pattern - SHOULD BE DETECTED
app.post('/test-callback', (req, res) => {
    const userInput = req.body.userInput;
    
    const http = require('http');
    http.get(`http://api.example.com/${userInput}`, (response) => {
        let data = '';
        response.on('data', (chunk) => { data += chunk; });
        response.on('end', () => {
            res.json(executePrivilegedOperation(data));
        });
    });
});

// TEST 19: Request with Custom Headers - SHOULD BE DETECTED
app.post('/test-headers', async (req, res) => {
    const apiKey = req.body.apiKey;
    const response = await axios.get('https://api.example.com/data', {
        headers: { 'X-API-Key': apiKey }
    });
    return res.json(executePrivilegedOperation(response.data));
});

// TEST 20: POST with Form Data - SHOULD BE DETECTED
app.post('/test-form', async (req, res) => {
    const formData = req.body;
    const response = await axios.post('https://api.example.com/submit', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return res.json(executePrivilegedOperation(response.data));
});

// TEST 21: Internal Data Only - SHOULD NOT BE DETECTED
app.get('/test-internal', (req, res) => {
    const internalConfig = 'internal-system-config';
    const systemUser = { role: 'admin' };
    return res.json(executePrivilegedOperation(systemUser.role));
});

// TEST 22: Hardcoded Values - SHOULD NOT BE DETECTED
app.get('/test-hardcoded', async (req, res) => {
    const hardcodedData = 'static-data';
    const response = await axios.get('https://api.example.com/config');
    // Using hardcoded data, not response data
    return res.json(executePrivilegedOperation(hardcodedData));
});

// TEST 23: Configuration Only - SHOULD NOT BE DETECTED
app.get('/test-config', async (req, res) => {
    const config = { apiUrl: 'https://api.example.com' };
    // Fetching config but not using response data in privileged op
    await axios.get(config.apiUrl);
    return res.json(executePrivilegedOperation('success'));
});

// Privileged operation (security-sensitive function)
function executePrivilegedOperation(data) {
    // Simulates a security-sensitive operation
    return { status: 'PRIVILEGED', data: data };
}

// Async version for testing async patterns
async function executePrivilegedOperationAsync(data) {
    await new Promise(resolve => setTimeout(resolve, 100));
    return { status: 'PRIVILEGED', data: data };
}

// Start server
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Test server running on port ${PORT}`);
});

/*
 * Expected Results:
 * ✅ 20 flows should be detected (tests 1-20)
 * ❌ 3 flows should NOT be detected (tests 21-23)
 * 
 * Test Categories:
 * - HTTP Clients: axios, fetch, node-fetch (tests 1-4, 13, 16-20)
 * - gRPC: protobuf service calls (test 5)
 * - Message Queues: Kafka, RabbitMQ (tests 6-7)
 * - Data Stores: Redis (test 8)
 * - GraphQL: HTTP-based queries (test 9)
 * - Other Protocols: WebSocket, Database (tests 10, 15)
 * - Complex Flows: chained calls, multiple outbound (tests 11-12, 14)
 * - Async Patterns: async/await, promises, callbacks (tests 16-18)
 * - Negative Cases: internal data only (tests 21-23)
 * 
 * Outbound Sink Patterns to Detect:
 * 1. axios.get() / axios.post() / axios() with user-controlled data
 * 2. fetch() with user-controlled URLs or body
 * 3. kafkaProducer.send() with user-controlled messages
 * 4. channel.sendToQueue() with user-controlled messages
 * 5. redisClient.set() / redisClient.publish() with user-controlled data
 * 6. grpcStub.MethodName() with user-controlled arguments
 * 7. HTTP requests in callbacks/promises with user data
 * 
 * Source Patterns:
 * 1. Express route handlers: req.body, req.params, req.query
 * 2. Request properties: req.body.*, req.query.*, req.params.*
 * 
 * Privileged Sink:
 * - executePrivilegedOperation() function calls
 */

module.exports = app;