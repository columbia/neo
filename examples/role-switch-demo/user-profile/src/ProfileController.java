package demo;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class ProfileController {

    private final RestTemplate restTemplate = new RestTemplate();

    @PreAuthorize("isAuthenticated()")
    @PostMapping("/updateProfile")
    public String updateProfile(@RequestBody ProfileRequest req) {
        String username = getUsername();
        String token = getToken();

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + token);

        Map<String, Object> data = Map.of("username", username, "role", req.getRole());
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(data, headers);

        // forward the (attacker-controlled) role to the Python service
        return restTemplate.postForObject(
            "http://localhost:5000/setUserRole", entity, String.class);
    }

    private String getUsername() { return "alice"; }
    private String getToken() { return "..."; }
}
