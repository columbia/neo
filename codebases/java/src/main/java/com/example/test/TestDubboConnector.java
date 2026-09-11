package com.example.test.dubbo;

import org.apache.dubbo.config.annotation.DubboReference;
import org.apache.dubbo.config.annotation.DubboService;
import org.springframework.stereotype.Component;
import java.io.Serializable;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// ========== DUBBO SERVICE INTERFACES (The Contracts) ==========

interface UserDubboService {
    DubboUserDto getUserById(String userId);
    DubboUserDto createUser(String name, String email);
}

interface PaymentDubboService {
    DubboPaymentResult processPayment(String userId, double amount);
}

// ========== DUBBO PROVIDERS (Service Implementations) ==========

@DubboService(interfaceClass = UserDubboService.class)
class UserDubboServiceImpl implements UserDubboService {
    private final Map<String, DubboUserDto> userDb = new ConcurrentHashMap<>();
    @Override
    public DubboUserDto getUserById(String userId) {
        System.out.println("DUBBO-USER-SVC: Received getUserById for " + userId);
        return userDb.getOrDefault(userId, new DubboUserDto("0", "Default", "default@dubbo.com"));
    }
    @Override
    public DubboUserDto createUser(String name, String email) {
        System.out.println("DUBBO-USER-SVC: Received createUser for " + name);
        String newId = "dubbo-" + (userDb.size() + 1);
        DubboUserDto user = new DubboUserDto(newId, name, email);
        userDb.put(newId, user);
        return user;
    }
}

@DubboService(interfaceClass = PaymentDubboService.class)
class PaymentDubboServiceImpl implements PaymentDubboService {
    @Override
    public DubboPaymentResult processPayment(String userId, double amount) {
        System.out.println("DUBBO-PAYMENT-SVC: Processing payment of " + amount + " for user " + userId);
        boolean success = Math.random() > 0.1; // 90% success rate
        return new DubboPaymentResult(success, "txn-" + (int)(Math.random()*10000));
    }
}

// ========== DUBBO CONSUMER (Orchestrating Business Logic) ==========

@Component
class DubboBusinessService {
    @DubboReference(check = false, interfaceClass = UserDubboService.class)
    private UserDubboService userDubboService;
    @DubboReference(check = false, interfaceClass = PaymentDubboService.class)
    private PaymentDubboService paymentDubboService;

    public void onboardNewUserAndMakePayment(String name, String email, double paymentAmount) {
        System.out.println("\nDUBBO-BIZ: Starting user onboarding flow for " + name);
        
        // 1. Call User service to create a user
        DubboUserDto newUser = userDubboService.createUser(name, email);
        System.out.println("DUBBO-BIZ: User created with ID: " + newUser.getId());

        // 2. Call Payment service to process a payment for the new user
        if (newUser != null && newUser.getId() != null) {
            DubboPaymentResult paymentResult = paymentDubboService.processPayment(newUser.getId(), paymentAmount);
            System.out.println("DUBBO-BIZ: Payment result: " + (paymentResult.isSuccess() ? "SUCCESS" : "FAILED"));
        }
    }
}

// ========== DATA TRANSFER OBJECTS (DTOs) ==========

class DubboUserDto implements Serializable {
    private String id, name, email;
    public DubboUserDto() {}
    public DubboUserDto(String i, String n, String e) { id=i; name=n; email=e; }
    public String getId() { return id; }
    public String getName() { return name; }
    // setters omitted for brevity
}

class DubboPaymentResult implements Serializable {
    private boolean success;
    private String transactionId;
    public DubboPaymentResult() {}
    public DubboPaymentResult(boolean s, String t) { success=s; transactionId=t; }
    public boolean isSuccess() { return success; }
    public String getTransactionId() { return transactionId; }
}
