package tests

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-resty/resty/v2"
)

// ========== DATA MODELS ==========

type HTTPUser struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

type HTTPPayment struct {
	Success       bool    `json:"success"`
	TransactionID string  `json:"transaction_id"`
	UserID        string  `json:"user_id"`
	Amount        float64 `json:"amount"`
}

type HTTPCreateUserRequest struct {
	Name  string `json:"name" binding:"required"`
	Email string `json:"email" binding:"required,email"`
}

type ProcessPaymentRequest struct {
	UserID string  `json:"user_id" binding:"required"`
	Amount float64 `json:"amount" binding:"required,gt=0"`
}

// ========== HTTP USER SERVICE ==========

type HTTPUserService struct {
	userDB map[string]*HTTPUser
	mu     sync.RWMutex
	server *http.Server
}

func NewHTTPUserService() *HTTPUserService {
	return &HTTPUserService{
		userDB: make(map[string]*HTTPUser),
	}
}

func (s *HTTPUserService) Start(port int) error {
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Recovery())

	router.GET("/users/:user_id", s.GetUser)
	router.POST("/users", s.CreateUser)
	router.PUT("/users/:user_id", s.UpdateUser)
	router.DELETE("/users/:user_id", s.DeleteUser)

	s.server = &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: router,
	}

	go func() {
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("HTTP-USER-SVC: Error starting server: %v", err)
		}
	}()

	time.Sleep(100 * time.Millisecond)
	log.Printf("HTTP-USER-SVC: Started on port %d", port)
	return nil
}

func (s *HTTPUserService) GetUser(c *gin.Context) {
	userID := c.Param("user_id")
	log.Printf("HTTP-USER-SVC: GetUser called for %s", userID)

	s.mu.RLock()
	user, exists := s.userDB[userID]
	s.mu.RUnlock()

	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	c.JSON(http.StatusOK, user)
}

func (s *HTTPUserService) CreateUser(c *gin.Context) {
	var req HTTPCreateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	log.Printf("HTTP-USER-SVC: CreateUser called for %s", req.Name)

	userID := fmt.Sprintf("http-user-%d", rand.Intn(9000)+1000)
	user := &HTTPUser{
		ID:    userID,
		Name:  req.Name,
		Email: req.Email,
	}

	s.mu.Lock()
	s.userDB[userID] = user
	s.mu.Unlock()

	c.JSON(http.StatusCreated, user)
}

func (s *HTTPUserService) UpdateUser(c *gin.Context) {
	userID := c.Param("user_id")
	var req HTTPCreateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	user, exists := s.userDB[userID]
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	user.Name = req.Name
	user.Email = req.Email
	c.JSON(http.StatusOK, user)
}

func (s *HTTPUserService) DeleteUser(c *gin.Context) {
	userID := c.Param("user_id")

	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.userDB[userID]; !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	delete(s.userDB, userID)
	c.JSON(http.StatusOK, gin.H{"message": "User deleted"})
}

func (s *HTTPUserService) Shutdown(ctx context.Context) error {
	if s.server != nil {
		return s.server.Shutdown(ctx)
	}
	return nil
}

// ========== HTTP PAYMENT SERVICE ==========

type HTTPPaymentService struct {
	server *http.Server
}

func NewHTTPPaymentService() *HTTPPaymentService {
	return &HTTPPaymentService{}
}

func (s *HTTPPaymentService) Start(port int) error {
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Recovery())

	router.POST("/payments", s.ProcessPayment)
	router.POST("/payments/refund", s.RefundPayment)

	s.server = &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: router,
	}

	go func() {
		if err := s.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("HTTP-PAYMENT-SVC: Error starting server: %v", err)
		}
	}()

	time.Sleep(100 * time.Millisecond)
	log.Printf("HTTP-PAYMENT-SVC: Started on port %d", port)
	return nil
}

func (s *HTTPPaymentService) ProcessPayment(c *gin.Context) {
	var req ProcessPaymentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	log.Printf("HTTP-PAYMENT-SVC: ProcessPayment called for user %s, amount %.2f", req.UserID, req.Amount)

	success := rand.Float64() > 0.1 // 90% success rate
	payment := &HTTPPayment{
		Success:       success,
		TransactionID: fmt.Sprintf("http-txn-%d", rand.Intn(9000)+1000),
		UserID:        req.UserID,
		Amount:        req.Amount,
	}

	c.JSON(http.StatusCreated, payment)
}

func (s *HTTPPaymentService) RefundPayment(c *gin.Context) {
	var req ProcessPaymentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	log.Printf("HTTP-PAYMENT-SVC: RefundPayment called for user %s, amount %.2f", req.UserID, req.Amount)

	payment := &HTTPPayment{
		Success:       true,
		TransactionID: fmt.Sprintf("http-refund-%d", rand.Intn(9000)+1000),
		UserID:        req.UserID,
		Amount:        req.Amount,
	}

	c.JSON(http.StatusOK, payment)
}

func (s *HTTPPaymentService) Shutdown(ctx context.Context) error {
	if s.server != nil {
		return s.server.Shutdown(ctx)
	}
	return nil
}

// ========== HTTP BUSINESS SERVICE (CLIENT) ==========

type HTTPBusinessService struct {
	userServiceURL    string
	paymentServiceURL string
	restyClient       *resty.Client
	httpClient        *http.Client
}

func NewHTTPBusinessService(userURL, paymentURL string) *HTTPBusinessService {
	return &HTTPBusinessService{
		userServiceURL:    userURL,
		paymentServiceURL: paymentURL,
		restyClient:       resty.New().SetTimeout(5 * time.Second),
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

// Sequential HTTP calls using Resty
func (s *HTTPBusinessService) OnboardUserWithResty(name, email string, amount float64) (*HTTPUser, *HTTPPayment, error) {
	log.Printf("\nHTTP-BIZ (Resty): Starting user onboarding for %s", name)

	// Step 1: Create user
	var user HTTPUser
	resp, err := s.restyClient.R().
		SetBody(HTTPCreateUserRequest{Name: name, Email: email}).
		SetResult(&user).
		Post(s.userServiceURL + "/users")

	if err != nil {
		return nil, nil, fmt.Errorf("user creation failed: %w", err)
	}

	if resp.StatusCode() != http.StatusCreated {
		return nil, nil, fmt.Errorf("user creation failed with status: %d", resp.StatusCode())
	}

	log.Printf("HTTP-BIZ (Resty): User created with ID: %s", user.ID)

	// Step 2: Process payment
	var payment HTTPPayment
	resp, err = s.restyClient.R().
		SetBody(ProcessPaymentRequest{UserID: user.ID, Amount: amount}).
		SetResult(&payment).
		Post(s.paymentServiceURL + "/payments")

	if err != nil {
		return &user, nil, fmt.Errorf("payment processing failed: %w", err)
	}

	if resp.StatusCode() != http.StatusCreated {
		return &user, nil, fmt.Errorf("payment failed with status: %d", resp.StatusCode())
	}

	log.Printf("HTTP-BIZ (Resty): Payment processed: %s", payment.TransactionID)
	return &user, &payment, nil
}

// Sequential HTTP calls using net/http
func (s *HTTPBusinessService) OnboardUserWithNetHTTP(name, email string, amount float64) (*HTTPUser, *HTTPPayment, error) {
	log.Printf("\nHTTP-BIZ (net/http): Starting user onboarding for %s", name)

	// Step 1: Create user
	userReq := HTTPCreateUserRequest{Name: name, Email: email}
	userJSON, err := json.Marshal(userReq)
	if err != nil {
		return nil, nil, err
	}

	resp, err := s.httpClient.Post(
		s.userServiceURL+"/users",
		"application/json",
		bytes.NewBuffer(userJSON),
	)
	if err != nil {
		return nil, nil, fmt.Errorf("user creation failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, nil, fmt.Errorf("user creation failed with status: %d", resp.StatusCode)
	}

	var user HTTPUser
	if err := json.NewDecoder(resp.Body).Decode(&user); err != nil {
		return nil, nil, err
	}

	log.Printf("HTTP-BIZ (net/http): User created with ID: %s", user.ID)

	// Step 2: Process payment
	paymentReq := ProcessPaymentRequest{UserID: user.ID, Amount: amount}
	paymentJSON, err := json.Marshal(paymentReq)
	if err != nil {
		return &user, nil, err
	}

	resp, err = s.httpClient.Post(
		s.paymentServiceURL+"/payments",
		"application/json",
		bytes.NewBuffer(paymentJSON),
	)
	if err != nil {
		return &user, nil, fmt.Errorf("payment processing failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return &user, nil, fmt.Errorf("payment failed with status: %d", resp.StatusCode)
	}

	var payment HTTPPayment
	if err := json.NewDecoder(resp.Body).Decode(&payment); err != nil {
		return &user, nil, err
	}

	log.Printf("HTTP-BIZ (net/http): Payment processed: %s", payment.TransactionID)
	return &user, &payment, nil
}

// Concurrent HTTP calls
func (s *HTTPBusinessService) GetUserProfile(userID string) (*HTTPUser, []*HTTPPayment, error) {
	log.Printf("\nHTTP-BIZ: Getting full profile for user %s (concurrent)", userID)

	var user HTTPUser
	var payments []*HTTPPayment
	var userErr, paymentErr error
	var wg sync.WaitGroup

	wg.Add(2)

	// Concurrent user fetch
	go func() {
		defer wg.Done()
		resp, err := s.restyClient.R().
			SetResult(&user).
			Get(s.userServiceURL + "/users/" + userID)

		if err != nil {
			userErr = err
			return
		}

		if resp.StatusCode() != http.StatusOK {
			userErr = fmt.Errorf("user fetch failed with status: %d", resp.StatusCode())
		}
	}()

	// Concurrent payment history fetch (simulated endpoint)
	go func() {
		defer wg.Done()
		// In real scenario, would call GET /users/{id}/payments
		payments = []*HTTPPayment{
			{
				Success:       true,
				TransactionID: "txn-001",
				UserID:        userID,
				Amount:        99.99,
			},
		}
	}()

	wg.Wait()

	if userErr != nil {
		return nil, nil, userErr
	}

	log.Printf("HTTP-BIZ: Profile retrieved successfully")
	return &user, payments, paymentErr
}

// Context-aware HTTP call
func (s *HTTPBusinessService) GetUserWithContext(ctx context.Context, userID string) (*HTTPUser, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", s.userServiceURL+"/users/"+userID, nil)
	if err != nil {
		return nil, err
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("user fetch failed with status: %d", resp.StatusCode)
	}

	var user HTTPUser
	if err := json.NewDecoder(resp.Body).Decode(&user); err != nil {
		return nil, err
	}

	return &user, nil
}

// Error handling pattern
func (s *HTTPBusinessService) OnboardWithRetry(name, email string, amount float64, maxRetries int) (*HTTPUser, *HTTPPayment, error) {
	var lastErr error

	for i := 0; i < maxRetries; i++ {
		user, payment, err := s.OnboardUserWithResty(name, email, amount)
		if err == nil {
			return user, payment, nil
		}

		lastErr = err
		log.Printf("HTTP-BIZ: Retry %d/%d failed: %v", i+1, maxRetries, err)
		time.Sleep(time.Duration(i+1) * 100 * time.Millisecond)
	}

	return nil, nil, fmt.Errorf("all retries failed: %w", lastErr)
}

// Chained HTTP calls
func (s *HTTPBusinessService) ChainedOperations(name, email string) error {
	log.Printf("\nHTTP-BIZ: Starting chained operations")

	// Create user
	user, _, err := s.OnboardUserWithResty(name, email, 100.0)
	if err != nil {
		return err
	}

	// Update user
	updateReq := HTTPCreateUserRequest{Name: user.Name + " Updated", Email: "updated-" + user.Email}
	_, err = s.restyClient.R().
		SetBody(updateReq).
		Put(s.userServiceURL + "/users/" + user.ID)
	if err != nil {
		return err
	}

	log.Printf("HTTP-BIZ: User updated")

	// Process refund
	_, err = s.restyClient.R().
		SetBody(ProcessPaymentRequest{UserID: user.ID, Amount: 50.0}).
		Post(s.paymentServiceURL + "/payments/refund")
	if err != nil {
		return err
	}

	log.Printf("HTTP-BIZ: Refund processed")
	return nil
}

// Multiple outbound calls
func (s *HTTPBusinessService) BroadcastToMultipleServices(userID string) error {
	log.Printf("\nHTTP-BIZ: Broadcasting to multiple services")

	services := []string{
		s.userServiceURL + "/users/" + userID,
		s.paymentServiceURL + "/payments",
	}

	var wg sync.WaitGroup
	errors := make(chan error, len(services))

	for _, serviceURL := range services {
		wg.Add(1)
		go func(url string) {
			defer wg.Done()
			_, err := s.restyClient.R().Get(url)
			if err != nil {
				errors <- err
			}
		}(serviceURL)
	}

	wg.Wait()
	close(errors)

	for err := range errors {
		if err != nil {
			return err
		}
	}

	log.Printf("HTTP-BIZ: Broadcast completed")
	return nil
}

// Raw HTTP request builder
func (s *HTTPBusinessService) RawHTTPCall(method, url string, body interface{}) ([]byte, error) {
	var bodyReader io.Reader

	if body != nil {
		jsonData, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		bodyReader = bytes.NewBuffer(jsonData)
	}

	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	return io.ReadAll(resp.Body)
}