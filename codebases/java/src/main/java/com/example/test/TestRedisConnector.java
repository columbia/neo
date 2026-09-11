package com.example.test.redis;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.listener.adapter.MessageListenerAdapter;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;

// ========== REDIS CONFIGURATION (For Pub/Sub) ==========
@Configuration
class RedisConfig {
    @Bean
    RedisMessageListenerContainer container(RedisConnectionFactory connectionFactory, MessageListenerAdapter listenerAdapter) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.addMessageListener(listenerAdapter, new ChannelTopic("user:notifications"));
        return container;
    }

    @Bean
    MessageListenerAdapter listenerAdapter(RedisSubscriber subscriber) {
        return new MessageListenerAdapter(subscriber, "receiveMessage");
    }
}

// ========== REDIS SERVICE (Key-Value & Pub/Sub Operations) ==========

@Service
class RedisCacheService {

    @Autowired
    private StringRedisTemplate template; // Used for simple key-value operations
    @Autowired
    private ObjectMapper objectMapper;

    // Outbound SET operation
    public void cacheUserProfile(RedisUser user) {
        try {
            System.out.println("REDIS-CACHE [SET]: Caching profile for user " + user.getName());
            String userJson = objectMapper.writeValueAsString(user);
            // Key format: "user:profile:<userId>"
            template.opsForValue().set("user:profile:" + user.getId(), userJson);
        } catch (Exception e) { e.printStackTrace(); }
    }

    // Outbound GET operation
    public RedisUser getCachedUserProfile(String userId) {
        try {
            System.out.println("REDIS-CACHE [GET]: Retrieving cached profile for user " + userId);
            String userJson = template.opsForValue().get("user:profile:" + userId);
            return userJson != null ? objectMapper.readValue(userJson, RedisUser.class) : null;
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }
}

@Service
class RedisPublisher {
    @Autowired
    private StringRedisTemplate template;

    // Outbound PUBLISH operation
    public void publishUserNotification(String message) {
        System.out.println("REDIS-PUB/SUB [PUBLISH]: Publishing message to 'user:notifications' channel.");
        template.convertAndSend("user:notifications", message);
    }
}

// ========== REDIS SUBSCRIBER (Inbound Message) ==========
@Service
class RedisSubscriber {
    // Inbound message handler
    public void receiveMessage(String message) {
        System.out.println("REDIS-PUB/SUB [SUBSCRIBE]: Received message: '" + message + "'");
    }
}


// ========== BUSINESS LOGIC DEMONSTRATION ==========
@Service
class RedisBusinessService {
    @Autowired private RedisCacheService cacheService;
    @Autowired private RedisPublisher publisher;

    public void runRedisFlow() {
        System.out.println("\n--- Testing Redis ---");
        // 1. Caching flow (SET/GET)
        RedisUser user = new RedisUser("redis-123", "Redis User", "redis.user@example.com");
        cacheService.cacheUserProfile(user);
        RedisUser cachedUser = cacheService.getCachedUserProfile("redis-123");
        System.out.println("Flow complete. Retrieved from cache: " + (cachedUser != null ? cachedUser.getName() : "null"));

        // 2. Pub/Sub flow (PUBLISH/SUBSCRIBE)
        publisher.publishUserNotification("Your profile has been updated!");
    }
}

// ========== DTO for Redis examples ==========
class RedisUser {
    private String id;
    private String name;
    private String email;
    public RedisUser() {}
    public RedisUser(String i, String n, String e) { id=i; name=n; email=e; }
    public String getId() { return id; }
    public String getName() { return name; }
    public String getEmail() { return email; }
}
