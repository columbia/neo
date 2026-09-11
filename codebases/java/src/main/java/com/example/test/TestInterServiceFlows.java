package com.example.test.interservice;


import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.apache.dubbo.config.annotation.DubboReference;
import org.springframework.cloud.openfeign.FeignClient;

/**
 * Single file test for inter-service taint flow validation.
 * Run your CodeQL query on this file to validate InterServiceModels.
 */
@RestController
public class TestInterServiceFlows {
    
    private RestTemplate restTemplate = new RestTemplate();
    private KafkaTemplate<String, String> kafkaTemplate;
    
    @DubboReference
    private UserService userService;
    
    private ExternalApiClient externalApi;
    
    // TEST 1: HTTP Client Taint Flow - SHOULD BE DETECTED
    @PostMapping("/test-http")
    public String testHttpFlow(@RequestParam String userInput) {
        String response = restTemplate.getForObject("https://api.example.com/" + userInput, String.class);
        return executePrivilegedOperation(response);
    }
    
    // TEST 2: Dubbo Service Taint Flow - SHOULD BE DETECTED
    @GetMapping("/test-dubbo")
    public String testDubboFlow(@RequestParam String userId) {
        User user = userService.getUser(userId);
        return executePrivilegedOperation(user.getRole());
    }
    
    // TEST 3: Kafka Outbound - SHOULD BE DETECTED
    @PostMapping("/test-kafka") 
    public String testKafkaFlow(@RequestParam String message) {
        kafkaTemplate.send("test-topic", message);
        return "Message sent";
    }
    
    // TEST 4: Feign Client Flow - SHOULD BE DETECTED
    @PostMapping("/test-feign")
    public String testFeignFlow(@RequestBody UserRequest request) {
        ApiResponse response = externalApi.createUser(request);
        return executePrivilegedOperation(response.getData());
    }
    
    // TEST 5: Chained Calls - SHOULD BE DETECTED
    @PostMapping("/test-chain")
    public String testChainedFlow(@RequestParam String input) {
        String httpResponse = restTemplate.getForObject("https://api.example.com/" + input, String.class);
        User user = userService.processData(httpResponse);
        return executePrivilegedOperation(user.getRole());
    }
    
    // TEST 6: Internal Data Only - SHOULD NOT BE DETECTED
    @GetMapping("/test-internal")
    public String testInternalFlow() {
        String internalConfig = "internal-config";
        User systemUser = userService.getSystemUser();
        return executePrivilegedOperation(systemUser.getRole());
    }
    
    private String executePrivilegedOperation(String data) {
        return "PRIVILEGED: " + data;
    }
}

// Supporting classes in same file
interface UserService {
    User getUser(String userId);
    User processData(String data);
    User getSystemUser();
}

@FeignClient(name = "external-api", url = "https://external.example.com")
interface ExternalApiClient {
    @PostMapping("/users")
    ApiResponse createUser(@RequestBody UserRequest request);
}

class User {
    private String role;
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
}

class UserRequest {
    private String name;
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
}

class ApiResponse {
    private String data;
    public String getData() { return data; }
    public void setData(String data) { this.data = data; }
}

/*
 * Expected Results:
 * ✅ 5 flows should be detected (tests 1-5)
 * ❌ 1 flow should NOT be detected (test 6)
 */