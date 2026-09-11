// TestMicroservices.java - Complete test program for HttpConnector queries

package com.example.test;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.stereotype.Controller;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.MediaType;
import java.util.List;
import java.util.Arrays;

// ========== FEIGN CLIENT (Outbound HTTP) ==========

@FeignClient(name = "account-service", url = "http://localhost:8081")
interface AccountServiceClient {

    @RequestMapping(method = RequestMethod.GET, value = "/accounts/{accountName}", 
                   consumes = MediaType.APPLICATION_JSON_VALUE)
    String getAccount(@PathVariable("accountName") String accountName);

    @PostMapping(value = "/accounts", consumes = MediaType.APPLICATION_JSON_VALUE)
    Account createAccount(@RequestBody Account account);

    @GetMapping("/accounts")
    List<Account> getAllAccounts(@RequestParam("status") String status);
}

@FeignClient(name = "payment-service")
interface PaymentServiceClient {

    @PostMapping("/payments")
    PaymentResult processPayment(@RequestBody PaymentRequest request);

    @GetMapping("/payments/{id}")
    Payment getPayment(@PathVariable("id") String paymentId);
}

// ========== SPRING CONTROLLERS (Inbound HTTP) ==========

@RestController
@RequestMapping("/api/users")
class UserController {

    @GetMapping("/{userId}")
    User getUser(@PathVariable("userId") String userId) {
        return new User(userId, "John Doe");
    }

    @PostMapping
    User createUser(@RequestBody User user, 
                          @RequestHeader("Authorization") String auth) {
        return user;
    }

    @PutMapping("/{userId}")
    User updateUser(@PathVariable("userId") String userId,
                          @RequestBody User user,
                          @RequestParam("notify") boolean notify) {
        return user;
    }
}

@Controller
class OrderController {

    @RequestMapping(method = RequestMethod.POST, value = "/orders")
    @ResponseBody
    Order createOrder(@RequestBody Order order,
                           @RequestParam("priority") String priority) {
        return order;
    }

    @GetMapping("/orders/{orderId}")
    @ResponseBody
    Order getOrder(@PathVariable("orderId") String orderId) {
        return new Order(orderId);
    }
}

// ========== CONTROLLERS THAT MATCH FEIGN CLIENTS ==========

// Controller that matches AccountServiceClient calls
@RestController
@RequestMapping("/accounts")
class AccountController {

    @GetMapping("/{accountName}")
    String getAccount(@PathVariable("accountName") String accountName) {
        return "Account info for: " + accountName;
    }

    @PostMapping
    Account createAccount(@RequestBody Account account) {
        return account;
    }

    @GetMapping
    List<Account> getAllAccounts(@RequestParam("status") String status) {
        return Arrays.asList(new Account("acc1"), new Account("acc2"));
    }
}

// Controller that matches PaymentServiceClient calls  
@RestController
@RequestMapping("/payments")
class PaymentController {

    @PostMapping
    PaymentResult processPayment(@RequestBody PaymentRequest request) {
        PaymentResult result = new PaymentResult();
        return result;
    }

    @GetMapping("/{id}")
    Payment getPayment(@PathVariable("id") String paymentId) {
        return new Payment();
    }
}

// Controller that matches RestTemplate calls
@RestController
@RequestMapping("/users")
class UsersController {

    @PostMapping
    User createUser(@RequestBody User user) {
        return user;
    }

    @GetMapping("/{id}")
    User getUser(@PathVariable("id") String userId) {
        return new User(userId, "External User");
    }
}

// ========== SERVICE CLASS (Uses Feign Clients) ==========

@Service
class BusinessService {
    
    private final AccountServiceClient accountClient;
    private final PaymentServiceClient paymentClient;
    private final RestTemplate restTemplate;

    BusinessService(AccountServiceClient accountClient, 
                          PaymentServiceClient paymentClient,
                          RestTemplate restTemplate) {
        this.accountClient = accountClient;
        this.paymentClient = paymentClient;
        this.restTemplate = restTemplate;
    }

    // Method that makes Feign client calls
    void processUserAccount(String userId, Account account) {
        // This should be detected as HttpFeignConnectorOut
        String accountInfo = accountClient.getAccount(userId);
        Account newAccount = accountClient.createAccount(account);
        
        // This should also be detected
        PaymentRequest paymentReq = new PaymentRequest(account.getAmount());
        PaymentResult result = paymentClient.processPayment(paymentReq);
    }

    // Method that makes RestTemplate calls  
    void callExternalService(String data) {
        // This should be detected as HttpRestTemplateConnectorOut
        String url = "http://external-service/api/data";
        String response = restTemplate.getForObject(url, String.class);
        
        User user = new User("123", data);
        User created = restTemplate.postForObject("http://user-service/users", user, User.class);
    }

    // Method with tainted data flow
    void handleUserInput(String untrustedInput) {
        // Tainted data sent to external service
        Account account = new Account(untrustedInput);
        accountClient.createAccount(account);  // ← Potential security issue
    }
}

// ========== DATA CLASSES ==========

class User {
    private String id;
    private String name;
    
    User(String id, String name) {
        this.id = id;
        this.name = name;
    }
    
    // getters/setters...
    String getId() { return id; }
    String getName() { return name; }
}

class Account {
    private String accountId;
    private double amount;
    
    Account(String accountId) {
        this.accountId = accountId;
    }
    
    double getAmount() { return amount; }
    // getters/setters...
}

class Order {
    private String orderId;
    
    Order(String orderId) {
        this.orderId = orderId;
    }
    
    // getters/setters...
}

class PaymentRequest {
    private double amount;
    
    PaymentRequest(double amount) {
        this.amount = amount;
    }
    
    // getters/setters...
}

class PaymentResult {
    private boolean success;
    
    // getters/setters...
}

class Payment {
    private String id;
    
    // getters/setters...
}