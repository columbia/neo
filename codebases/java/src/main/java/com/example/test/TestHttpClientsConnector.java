package com.example.test.httpclients;

import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import cn.hutool.http.HttpUtil;

// ========== A GENERIC CONTROLLER FOR HTTP CLIENTS TO CALL (Inbound HTTP) ==========

@RestController
@RequestMapping("/api/generic-products")
class GenericHttpProductController {
    @GetMapping("/{id}")
    public ProductDto getProduct(@PathVariable String id) {
        System.out.println("GENERIC-CTRL: GET request received for product " + id);
        return new ProductDto(id, "Generic Product", 99.99);
    }
    @PostMapping
    public ProductDto createProduct(@RequestBody ProductDto product) {
        System.out.println("GENERIC-CTRL: POST request received to create product " + product.getName());
        product.setId("prod-" + (int)(Math.random()*1000));
        return product;
    }
}

// ========== 1. JDK 11+ NATIVE HTTP CLIENT (Outbound HTTP) ==========

@Service
class JdkNativeHttpService {
    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public void executeRequests() throws Exception {
        System.out.println("\n--- Testing JDK Native HttpClient ---");
        // GET request
        HttpRequest getRequest = HttpRequest.newBuilder()
                .uri(URI.create("http://localhost:8080/api/generic-products/123"))
                .build();
        HttpResponse<String> getResponse = httpClient.send(getRequest, HttpResponse.BodyHandlers.ofString());
        System.out.println("JDK-GET Response: " + getResponse.body());

        // POST request
        ProductDto newProduct = new ProductDto(null, "JDK Product", 150.0);
        String requestBody = objectMapper.writeValueAsString(newProduct);
        HttpRequest postRequest = HttpRequest.newBuilder()
                .uri(URI.create("http://localhost:8080/api/generic-products"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();
        HttpResponse<String> postResponse = httpClient.send(postRequest, HttpResponse.BodyHandlers.ofString());
        System.out.println("JDK-POST Response: " + postResponse.body());
    }
}

// ========== 2. APACHE HTTPCLIENT (Outbound HTTP) ==========

@Service
class ApacheHttpService {
    public void executeRequests() throws Exception {
        System.out.println("\n--- Testing Apache HttpClient ---");
        try (CloseableHttpClient client = HttpClients.createDefault()) {
            // GET request
            HttpGet httpGet = new HttpGet("http://localhost:8080/api/generic-products/456");
            try (CloseableHttpResponse response = client.execute(httpGet)) {
                System.out.println("Apache-GET Response: " + EntityUtils.toString(response.getEntity()));
            }

            // POST request
            HttpPost httpPost = new HttpPost("http://localhost:8080/api/generic-products");
            ProductDto newProduct = new ProductDto(null, "Apache Product", 250.0);
            String json = new ObjectMapper().writeValueAsString(newProduct);
            httpPost.setEntity(new StringEntity(json));
            httpPost.setHeader("Content-type", "application/json");
            try (CloseableHttpResponse response = client.execute(httpPost)) {
                System.out.println("Apache-POST Response: " + EntityUtils.toString(response.getEntity()));
            }
        }
    }
}

// ========== 3. HUTOOL-HTTP (Outbound HTTP) ==========

@Service
class HutoolHttpService {
    public void executeRequests() {
        System.out.println("\n--- Testing Hutool-http ---");
        // GET request
        String getResponse = HttpUtil.get("http://localhost:8080/api/generic-products/789");
        System.out.println("Hutool-GET Response: " + getResponse);

        // POST request
        ProductDto newProduct = new ProductDto(null, "Hutool Product", 350.0);
        String jsonBody = new ObjectMapper().valueToTree(newProduct).toString();
        String postResponse = HttpUtil.post("http://localhost:8080/api/generic-products", jsonBody);
        System.out.println("Hutool-POST Response: " + postResponse);
    }
}


// ========== DTO for HTTP examples ==========
class ProductDto {
    private String id;
    private String name;
    private double price;
    public ProductDto() {}
    public ProductDto(String i, String n, double p) { id=i; name=n; price=p;}
    public String getId() { return id; }
    public String getName() { return name; }
    public double getPrice() { return price; }
    public void setId(String id) { this.id = id; }
    public void setName(String name) { this.name = name; }
    public void setPrice(double price) { this.price = price; }
}
