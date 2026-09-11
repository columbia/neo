package com.example.test.graphql;

import org.springframework.graphql.data.method.annotation.Argument;
import org.springframework.graphql.data.method.annotation.MutationMapping;
import org.springframework.graphql.data.method.annotation.QueryMapping;
import org.springframework.graphql.data.method.annotation.SchemaMapping;
import org.springframework.stereotype.Controller;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
// Real Spring imports for GraphQL WebClient
import org.springframework.graphql.client.GraphQlClient;
import org.springframework.graphql.client.HttpGraphQlClient;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.client.RestTemplate;

import java.util.Map;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/*
==================== COMPREHENSIVE GRAPHQL TEST FILE ====================
Updated version with real Spring classes and proper dependencies
*/

// =============================================================================
// 1. SERVER-SIDE: GRAPHQL ENDPOINTS (Your original code)
// =============================================================================

@Controller
class GraphqlController {

    private final Map<String, GraphqlUser> userDatabase = new ConcurrentHashMap<>();
    private final Map<String, GraphqlOrder> orderDatabase = new ConcurrentHashMap<>();

    public GraphqlController() {
        GraphqlUser user1 = new GraphqlUser("1", "GraphQL Jane", "jane@graphql.com");
        GraphqlUser user2 = new GraphqlUser("2", "GraphQL John", "john@graphql.com");
        userDatabase.put("1", user1);
        userDatabase.put("2", user2);
        orderDatabase.put("101", new GraphqlOrder("101", "Laptop", 1200.50, "1"));
        orderDatabase.put("102", new GraphqlOrder("102", "Mouse", 25.00, "1"));
        orderDatabase.put("103", new GraphqlOrder("103", "Keyboard", 75.75, "2"));
    }

    @QueryMapping
    public GraphqlUser userById(@Argument String id) {
        System.out.println("GQL-QUERY: Fetching user by id: " + id);
        return userDatabase.get(id);
    }
    
    @QueryMapping
    public GraphqlOrder orderById(@Argument String id) {
        System.out.println("GQL-QUERY: Fetching order by id: " + id);
        return orderDatabase.get(id);
    }

    @MutationMapping
    public GraphqlUser createUser(@Argument GraphqlUserInput userInput) {
        String newId = String.valueOf(userDatabase.size() + 1);
        GraphqlUser newUser = new GraphqlUser(newId, userInput.getName(), userInput.getEmail());
        userDatabase.put(newId, newUser);
        System.out.println("GQL-MUTATION: Created new user: " + newUser.getName());
        return newUser;
    }
    
    @SchemaMapping(typeName="GraphqlUser", field="orders")
    public List<GraphqlOrder> getOrdersForUser(GraphqlUser user) {
        System.out.println("GQL-RESOLVER: Fetching orders for user " + user.getId());
        return orderDatabase.values().stream()
                .filter(order -> order.getUserId().equals(user.getId()))
                .collect(Collectors.toList());
    }
    
    @SchemaMapping(typeName="GraphqlOrder", field="user")
    public GraphqlUser getUserForOrder(GraphqlOrder order) {
        System.out.println("GQL-RESOLVER: Fetching user " + order.getUserId() + " for order " + order.getId());
        return userDatabase.get(order.getUserId());
    }
}

// =============================================================================
// 2. CLIENT-SIDE: GRAPHQL CLIENT INTERFACES (Package-private to avoid errors)
// =============================================================================

/**
 * GraphQL client interface for User operations
 * This should be detected as GraphQLClientInterface and methods as GraphQLClient
 */
interface UserGraphQLClient {
    GraphqlUser queryUserById(String id);
    List<GraphqlUser> queryAllUsers();
    GraphqlUser mutateCreateUser(GraphqlUserInput userInput);
    GraphqlUser mutateUpdateUser(String id, GraphqlUserInput userInput);
}

/**
 * GraphQL client interface for Order operations
 * This should be detected as GraphQLClientInterface and methods as GraphQLClient
 */
interface OrderGraphQLService {
    GraphqlOrder queryOrderById(String id);
    List<GraphqlOrder> queryOrdersByUserId(String userId);
    GraphqlOrder mutateCreateOrder(GraphqlOrderInput orderInput);
}

/**
 * Another GraphQL client with different naming pattern
 */
interface PaymentGqlClient {
    PaymentResult queryPaymentStatus(String paymentId);
    PaymentResult mutateProcessPayment(PaymentRequest request);
    List<PaymentResult> executeGraphQLPaymentHistory(String userId);
}

// =============================================================================
// 3. SERVICE INVOCATIONS: CALLS TO GRAPHQL CLIENTS (Package-private)
// =============================================================================

/**
 * Service that uses GraphQL client interfaces
 * Calls should be detected as GraphQLCall
 */
@Service
class UserManagementService {
    
    @Autowired
    private UserGraphQLClient userGraphQLClient;
    
    @Autowired
    private OrderGraphQLService orderGraphQLService;
    
    public void processUserRegistration(String name, String email) {
        // GraphQL client interface calls - should be detected as GraphQLCall
        GraphqlUserInput userInput = new GraphqlUserInput();
        userInput.setName(name);
        userInput.setEmail(email);
        
        GraphqlUser newUser = userGraphQLClient.mutateCreateUser(userInput);  // ← GraphQLCall
        System.out.println("Created user via GraphQL: " + newUser.getId());
        
        // Another GraphQL call
        GraphqlUser retrievedUser = userGraphQLClient.queryUserById(newUser.getId());  // ← GraphQLCall
        System.out.println("Retrieved user: " + retrievedUser.getName());
    }
    
    public void processOrderHistory(String userId) {
        // More GraphQL calls
        GraphqlUser user = userGraphQLClient.queryUserById(userId);  // ← GraphQLCall
        List<GraphqlOrder> orders = orderGraphQLService.queryOrdersByUserId(userId);  // ← GraphQLCall
        
        System.out.println("User " + user.getName() + " has " + orders.size() + " orders");
    }
    
    public void processUserUpdate(String userId, String newName) {
        GraphqlUserInput updateInput = new GraphqlUserInput();
        updateInput.setName(newName);
        
        // Another GraphQL call
        GraphqlUser updatedUser = userGraphQLClient.mutateUpdateUser(userId, updateInput);  // ← GraphQLCall
        System.out.println("Updated user: " + updatedUser.getName());
    }
}

/**
 * Service that uses different GraphQL client
 */
@Service
class PaymentService {
    
    @Autowired
    private PaymentGqlClient paymentGqlClient;
    
    public void processPayment(String userId, double amount) {
        PaymentRequest request = new PaymentRequest(userId, amount);
        
        // GraphQL client call
        PaymentResult result = paymentGqlClient.mutateProcessPayment(request);  // ← GraphQLCall
        
        if (result.isSuccess()) {
            // Another GraphQL call
            PaymentResult status = paymentGqlClient.queryPaymentStatus(result.getPaymentId());  // ← GraphQLCall
            System.out.println("Payment processed: " + status.getPaymentId());
        }
    }
    
    public void getPaymentHistory(String userId) {
        // Another GraphQL call with different method pattern
        List<PaymentResult> history = paymentGqlClient.executeGraphQLPaymentHistory(userId);  // ← GraphQLCall
        System.out.println("Payment history: " + history.size() + " payments");
    }
}

// =============================================================================
// 4. SPRING GRAPHQL WEBCLIENT CALLS (Real Spring classes)
// =============================================================================

/**
 * Service that uses Spring GraphQL WebClient calls
 * Now using real Spring classes for proper CodeQL detection
 */
@Service
class GraphQLWebClientService {
    
    // Real Spring GraphQL client
    private GraphQlClient graphQlClient;
    
    public GraphQLWebClientService() {
        // Initialize with WebClient using the correct Spring GraphQL client setup for 2.7.x
        WebClient webClient = WebClient.builder()
            .baseUrl("http://localhost:8080/graphql")
            .build();
        this.graphQlClient = HttpGraphQlClient.builder(webClient).build();
    }
    
    public void executeUserQuery(String userId) {
        // Real Spring WebClient GraphQL calls - should be detected as GraphQLWebClientCall
        String query = "query { userById(id: \"" + userId + "\") { id name email } }";
        
        graphQlClient.document(query).execute();  // ← Should be GraphQLWebClientCall
        
        graphQlClient.documentName("getUserQuery")  // ← Should be GraphQLWebClientCall
                    .execute();
    }
    
    public void executeMutation(String name, String email) {
        String mutation = "mutation { createUser(userInput: { name: \"" + name + "\", email: \"" + email + "\" }) { id name } }";
        
        // Use execute() instead of executeSync() as executeSync() may not be available in all versions
        graphQlClient.document(mutation).execute();  // ← Should be GraphQLWebClientCall
    }
    
    public void executeWithVariables() {
        String query = "query GetUser($userId: ID!) { userById(id: $userId) { id name email } }";
        
        graphQlClient.document(query)
                    .variable("userId", "123")
                    .execute();  // ← Should be GraphQLWebClientCall
    }
}

// =============================================================================
// 5. HTTP GRAPHQL CALLS (Real Spring classes)
// =============================================================================

/**
 * Service that makes HTTP calls to GraphQL endpoints
 * Now using real Spring classes for proper CodeQL detection
 */
@Service
class GraphQLHttpService {
    
    private RestTemplate restTemplate;
    private WebClient webClient;
    
    public GraphQLHttpService() {
        this.restTemplate = new RestTemplate();
        this.webClient = WebClient.builder().build();
    }
    
    public void callGraphQLViaRestTemplate(String userId) {
        String graphqlQuery = "{\"query\": \"{ userById(id: \\\"" + userId + "\\\") { id name email } }\"}";
        
        // HTTP POST to GraphQL endpoint - should be detected as GraphQLHttpCall
        String response = restTemplate.postForObject(
            "http://localhost:8080/graphql",  // ← GraphQL endpoint URL
            graphqlQuery, 
            String.class
        );  // ← Should be GraphQLHttpCall
        
        System.out.println("GraphQL response: " + response);
    }
    
    public void callGraphQLViaWebClient(String orderId) {
        String graphqlQuery = "{\"query\": \"{ orderById(id: \\\"" + orderId + "\\\") { id productName amount } }\"}";
        
        // WebClient HTTP call to GraphQL - should be detected as GraphQLHttpCall
        webClient.post()
                .uri("http://api.example.com/graphql")  // ← GraphQL endpoint URL
                .bodyValue(graphqlQuery)
                .retrieve()  // ← Should be GraphQLHttpCall
                .bodyToMono(String.class)
                .block();
    }
    
    public void callExternalGraphQLService() {
        String mutation = "{\"mutation\": \"createOrder(input: { productName: \\\"Laptop\\\", amount: 1200.50 }) { id }\"}";
        
        // Another HTTP GraphQL call
        restTemplate.postForEntity(
            "https://external-service.com/graphql",  // ← External GraphQL service
            mutation,
            String.class
        );  // ← Should be GraphQLHttpCall
    }
    
    public void multipleGraphQLCalls() {
        // Multiple GraphQL calls in one method
        String userQuery = "{\"query\": \"{ userById(id: \\\"1\\\") { id name } }\"}";
        String orderQuery = "{\"query\": \"{ orderById(id: \\\"101\\\") { id productName } }\"}";
        
        restTemplate.postForObject("http://localhost:8080/graphql", userQuery, String.class);
        restTemplate.postForObject("http://localhost:8081/graphql", orderQuery, String.class);
        
        // WebClient calls too
        webClient.post().uri("http://api.example.com/graphql").bodyValue(userQuery).retrieve().bodyToMono(String.class).block();
        webClient.post().uri("http://api.example.com/graphql").bodyValue(orderQuery).retrieve().bodyToMono(String.class).block();
    }
}

// =============================================================================
// 6. MIXED GRAPHQL USAGE PATTERNS
// =============================================================================

/**
 * Service that demonstrates various GraphQL usage patterns
 */
@Service
class MixedGraphQLService {
    
    @Autowired
    private UserGraphQLClient userGraphQLClient;
    
    private GraphQlClient graphQlClient;
    private RestTemplate restTemplate;
    
    public MixedGraphQLService() {
        this.restTemplate = new RestTemplate();
        WebClient webClient = WebClient.builder()
            .baseUrl("http://localhost:8080/graphql")
            .build();
        this.graphQlClient = HttpGraphQlClient.builder(webClient).build();
    }
    
    public void demonstrateAllGraphQLPatterns(String userId) {
        // 1. GraphQL Client Interface Call
        GraphqlUser user = userGraphQLClient.queryUserById(userId);  // ← GraphQLCall
        
        // 2. Spring GraphQL WebClient Call
        String query = "query { userById(id: \"" + userId + "\") { orders { id productName } } }";
        graphQlClient.document(query).execute();  // ← GraphQLWebClientCall
        
        // 3. HTTP GraphQL Call via RestTemplate
        String graphqlPayload = "{\"query\": \"{ userById(id: \\\"" + userId + "\\\") { id name } }\"}";
        restTemplate.postForObject("http://localhost:8080/graphql", graphqlPayload, String.class);  // ← GraphQLHttpCall
        
        System.out.println("Demonstrated all GraphQL patterns for user: " + user.getName());
    }
}

// =============================================================================
// 7. DATA CLASSES AND TYPES (Same as before)
// =============================================================================

class GraphqlUser {
    private String id;
    private String name;
    private String email;
    
    public GraphqlUser(String id, String n, String e) { 
        this.id = id; this.name = n; this.email = e; 
    }
    
    public String getId() { return id; }
    public String getName() { return name; }
    public String getEmail() { return email; }
}

class GraphqlOrder {
    private String id;
    private String productName;
    private double amount;
    private String userId;
    
    public GraphqlOrder(String id, String p, double a, String uId) { 
        this.id = id; this.productName = p; this.amount = a; this.userId = uId; 
    }
    
    public String getId() { return id; }
    public String getProductName() { return productName; }
    public double getAmount() { return amount; }
    public String getUserId() { return userId; }
}

class GraphqlUserInput {
    private String name;
    private String email;
    
    public String getName() { return name; }
    public String getEmail() { return email; }
    public void setName(String n) { name = n; }
    public void setEmail(String e) { email = e; }
}

class GraphqlOrderInput {
    private String productName;
    private double amount;
    private String userId;
    
    public String getProductName() { return productName; }
    public double getAmount() { return amount; }
    public String getUserId() { return userId; }
    public void setProductName(String p) { productName = p; }
    public void setAmount(double a) { amount = a; }
    public void setUserId(String id) { userId = id; }
}

class PaymentRequest {
    private String userId;
    private double amount;
    
    public PaymentRequest(String userId, double amount) {
        this.userId = userId;
        this.amount = amount;
    }
    
    public String getUserId() { return userId; }
    public double getAmount() { return amount; }
}

class PaymentResult {
    private String paymentId;
    private boolean success;
    
    public String getPaymentId() { return paymentId; }
    public boolean isSuccess() { return success; }
}