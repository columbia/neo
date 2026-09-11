package com.example.test.kafka;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;

// ========== KAFKA PRODUCERS (Outbound Messaging for Multiple Services) ==========

@Service
class KafkaEventProducer {

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;
    @Autowired
    private ObjectMapper objectMapper;

    // Send a user-related event
    public void sendUserCreatedEvent(KafkaUserCreatedEvent event) {
        try {
            String jsonEvent = objectMapper.writeValueAsString(event);
            kafkaTemplate.send("user-events", event.getUserId(), jsonEvent);
        } catch (Exception e) { e.printStackTrace(); }
    }

    // Send a payment-related event
    public void sendPaymentProcessedEvent(KafkaPaymentProcessedEvent event) {
        try {
            String jsonEvent = objectMapper.writeValueAsString(event);
            kafkaTemplate.send("payment-events", event.getOrderId(), jsonEvent);
        } catch (Exception e) { e.printStackTrace(); }
    }
}

// ========== KAFKA CONSUMERS (Inbound Messaging for Multiple Services) ==========

@Service
class KafkaEventConsumer {
    @Autowired
    private ObjectMapper objectMapper;

    // Listens on the user topic
    @KafkaListener(topics = "user-events", groupId = "notification-service")
    public void consumeUserEvents(String message) {
        try {
            KafkaUserCreatedEvent event = objectMapper.readValue(message, KafkaUserCreatedEvent.class);
            System.out.println("KAFKA-NOTIFY: User created event received for user: " + event.getUserName());
            // Logic to send a welcome email, etc.
        } catch (Exception e) { e.printStackTrace(); }
    }

    // Listens on the payment topic
    @KafkaListener(topics = "payment-events", groupId = "order-service")
    public void consumePaymentEvents(String message) {
        try {
            KafkaPaymentProcessedEvent event = objectMapper.readValue(message, KafkaPaymentProcessedEvent.class);
            System.out.println("KAFKA-ORDER: Payment processed for order: " + event.getOrderId() + " with status: " + event.isSuccess());
            // Logic to update order status, etc.
        } catch (Exception e) { e.printStackTrace(); }
    }
}

// ========== SERVICE CLASS (Demonstrates Complex Flow) ==========

@Service
class KafkaBusinessService {
    
    private final KafkaEventProducer eventProducer;

    KafkaBusinessService(KafkaEventProducer eventProducer) {
        this.eventProducer = eventProducer;
    }

    // Business method that triggers multiple, decoupled events
    public void onboardNewUserAndProcessFirstOrder(String userName, String email, String orderId, double amount) {
        // 1. A new user is registered
        String userId = "user-" + (int)(Math.random() * 1000);
        System.out.println("KAFKA-BIZ: Onboarding user " + userName);
        eventProducer.sendUserCreatedEvent(new KafkaUserCreatedEvent(userId, userName, email));
        
        // 2. A payment is processed for their first order
        System.out.println("KAFKA-BIZ: Processing payment for order " + orderId);
        boolean paymentSuccess = amount < 1000; // Mock logic
        eventProducer.sendPaymentProcessedEvent(new KafkaPaymentProcessedEvent(orderId, userId, paymentSuccess));
    }
}

// ========== DATA CLASSES (DTOs for events) ==========

class KafkaUserCreatedEvent {
    private String userId;
    private String userName;
    private String email;
    public KafkaUserCreatedEvent() {}
    public KafkaUserCreatedEvent(String u, String n, String e) { userId = u; userName = n; email = e; }
    public String getUserId() { return userId; }
    public String getUserName() { return userName; }
    public void setUserId(String u) { userId = u; }
    public void setUserName(String n) { userName = n; }
    public void setEmail(String e) { email = e; }
}

class KafkaPaymentProcessedEvent {
    private String orderId;
    private String userId;
    private boolean success;
    public KafkaPaymentProcessedEvent() {}
    public KafkaPaymentProcessedEvent(String o, String u, boolean s) { orderId = o; userId = u; success = s; }
    public String getOrderId() { return orderId; }
    public String getUserId() { return userId; }
    public boolean isSuccess() { return success; }
    public void setOrderId(String o) { orderId = o; }
    public void setUserId(String u) { userId = u; }
    public void setSuccess(boolean s) { success = s; }
}
