package com.example.test.rabbitmq;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Component;
import java.io.Serializable;

@Configuration
class RabbitMqConfig {
    // Exchange for user-related events
    @Bean FanoutExchange userExchange() { return new FanoutExchange("user.events.exchange"); }
    // Exchange for order-related events
    @Bean DirectExchange orderExchange() { return new DirectExchange("order.events.exchange"); }

    // Queues for different services
    @Bean Queue notificationQueue() { return new Queue("notification.service.queue"); }
    @Bean Queue shippingQueue() { return new Queue("shipping.service.queue"); }

    // Bindings
    @Bean Binding userToNotificationBinding(FanoutExchange userExchange, Queue notificationQueue) {
        return BindingBuilder.bind(notificationQueue).to(userExchange);
    }
    @Bean Binding orderToShippingBinding(DirectExchange orderExchange, Queue shippingQueue) {
        return BindingBuilder.bind(shippingQueue).to(orderExchange).with("order.paid");
    }
}

// ========== RABBITMQ PRODUCER (Outbound Messaging) ==========
@Component
class RabbitMqEventProducer {
    @Autowired private RabbitTemplate rabbitTemplate;

    public void publishUserRegisteredEvent(RabbitUserRegisteredEvent event) {
        System.out.println("RABBIT-PUB: Publishing UserRegisteredEvent for " + event.getUserName());
        rabbitTemplate.convertAndSend("user.events.exchange", "", event); // Fanout, no routing key needed
    }
    public void publishOrderPaidEvent(RabbitOrderPaidEvent event) {
        System.out.println("RABBIT-PUB: Publishing OrderPaidEvent for order " + event.getOrderId());
        rabbitTemplate.convertAndSend("order.events.exchange", "order.paid", event);
    }
}

// ========== RABBITMQ CONSUMERS (Inbound Messaging) ==========
@Component
class RabbitMqEventConsumer {
    @RabbitListener(queues = "notification.service.queue")
    public void consumeUserRegistered(RabbitUserRegisteredEvent event) {
        System.out.println("RABBIT-CONSUMER [NotificationSvc]: Received UserRegisteredEvent for " + event.getUserName() + ". Sending welcome email.");
    }
    @RabbitListener(queues = "shipping.service.queue")
    public void consumeOrderPaid(RabbitOrderPaidEvent event) {
        System.out.println("RABBIT-CONSUMER [ShippingSvc]: Received OrderPaidEvent for order " + event.getOrderId() + ". Preparing for shipment.");
    }
}

// ========== BUSINESS SERVICE (Demonstrates usage) ==========
@Component
class RabbitMqBusinessService {
    private final RabbitMqEventProducer eventProducer;
    RabbitMqBusinessService(RabbitMqEventProducer p) { this.eventProducer = p; }

    public void processNewUserOrder(String userName, String email, String orderId, String address) {
        System.out.println("\nRABBIT-BIZ: Starting full order flow for " + userName);
        // 1. A new user registers
        eventProducer.publishUserRegisteredEvent(new RabbitUserRegisteredEvent(userName, email));
        // 2. The user's order is marked as paid
        eventProducer.publishOrderPaidEvent(new RabbitOrderPaidEvent(orderId, userName, address));
    }
}

// ========== DATA TRANSFER OBJECTS (DTOs) ==========
class RabbitUserRegisteredEvent implements Serializable {
    private String userName, email;
    public RabbitUserRegisteredEvent(String n, String e) { userName=n; email=e; }
    public String getUserName() { return userName; }
}
class RabbitOrderPaidEvent implements Serializable {
    private String orderId, userName, shippingAddress;
    public RabbitOrderPaidEvent(String o, String u, String a) { orderId=o; userName=u; shippingAddress=a; }
    public String getOrderId() { return orderId; }
}
