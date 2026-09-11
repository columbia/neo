package tests

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// ========== DATA MODELS ==========

type RedisUser struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	Timestamp time.Time `json:"timestamp"`
}

type RedisPayment struct {
	Success       bool      `json:"success"`
	TransactionID string    `json:"transaction_id"`
	UserID        string    `json:"user_id"`
	Amount        float64   `json:"amount"`
	Timestamp     time.Time `json:"timestamp"`
}

type RedisEvent struct {
	Type      string    `json:"type"`
	UserID    string    `json:"user_id,omitempty"`
	Timestamp time.Time `json:"timestamp"`
	Data      string    `json:"data"`
}

// ========== REDIS USER SERVICE ==========

type RedisUserService struct {
	client *redis.Client
	mu     sync.RWMutex
}

func NewRedisUserService(addr string) *RedisUserService {
	client := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     "",
		DB:           0,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     10,
	})

	return &RedisUserService{
		client: client,
	}
}

func (s *RedisUserService) Ping(ctx context.Context) error {
	return s.client.Ping(ctx).Err()
}

func (s *RedisUserService) CreateUser(ctx context.Context, name, email string) (*RedisUser, error) {
	log.Printf("REDIS-USER-SVC: Creating user %s", name)

	user := &RedisUser{
		ID:        fmt.Sprintf("redis-user-%d", time.Now().Unix()),
		Name:      name,
		Email:     email,
		Timestamp: time.Now(),
	}

	// Store user in Redis hash
	userKey := fmt.Sprintf("user:%s", user.ID)
	userMap := map[string]interface{}{
		"id":        user.ID,
		"name":      user.Name,
		"email":     user.Email,
		"timestamp": user.Timestamp.Format(time.RFC3339),
	}

	if err := s.client.HSet(ctx, userKey, userMap).Err(); err != nil {
		return nil, fmt.Errorf("failed to store user: %w", err)
	}

	// Add to user index
	if err := s.client.SAdd(ctx, "users:all", user.ID).Err(); err != nil {
		return nil, err
	}

	// Publish user created event
	event := RedisEvent{
		Type:      "USER_CREATED",
		UserID:    user.ID,
		Timestamp: time.Now(),
	}

	userData, _ := json.Marshal(user)
	event.Data = string(userData)
	eventJSON, _ := json.Marshal(event)

	if err := s.client.Publish(ctx, "user:events", eventJSON).Err(); err != nil {
		return nil, err
	}

	log.Printf("REDIS-USER-SVC: User created and event published: %s", user.ID)
	return user, nil
}

func (s *RedisUserService) GetUser(ctx context.Context, userID string) (*RedisUser, error) {
	userKey := fmt.Sprintf("user:%s", userID)
	result, err := s.client.HGetAll(ctx, userKey).Result()
	if err != nil {
		return nil, err
	}

	if len(result) == 0 {
		return nil, fmt.Errorf("user not found")
	}

	timestamp, _ := time.Parse(time.RFC3339, result["timestamp"])
	user := &RedisUser{
		ID:        result["id"],
		Name:      result["name"],
		Email:     result["email"],
		Timestamp: timestamp,
	}

	return user, nil
}

func (s *RedisUserService) UpdateUser(ctx context.Context, userID, name, email string) error {
	userKey := fmt.Sprintf("user:%s", userID)

	// Check if user exists
	exists, err := s.client.Exists(ctx, userKey).Result()
	if err != nil {
		return err
	}
	if exists == 0 {
		return fmt.Errorf("user not found")
	}

	// Update fields
	updates := map[string]interface{}{
		"name":      name,
		"email":     email,
		"timestamp": time.Now().Format(time.RFC3339),
	}

	if err := s.client.HSet(ctx, userKey, updates).Err(); err != nil {
		return err
	}

	// Publish update event
	event := RedisEvent{
		Type:      "USER_UPDATED",
		UserID:    userID,
		Timestamp: time.Now(),
		Data:      fmt.Sprintf(`{"name":"%s","email":"%s"}`, name, email),
	}

	eventJSON, _ := json.Marshal(event)
	s.client.Publish(ctx, "user:events", eventJSON)

	log.Printf("REDIS-USER-SVC: User updated: %s", userID)
	return nil
}

func (s *RedisUserService) DeleteUser(ctx context.Context, userID string) error {
	userKey := fmt.Sprintf("user:%s", userID)

	deleted, err := s.client.Del(ctx, userKey).Result()
	if err != nil {
		return err
	}

	if deleted == 0 {
		return fmt.Errorf("user not found")
	}

	// Remove from index
	s.client.SRem(ctx, "users:all", userID)

	// Publish delete event
	event := RedisEvent{
		Type:      "USER_DELETED",
		UserID:    userID,
		Timestamp: time.Now(),
	}

	eventJSON, _ := json.Marshal(event)
	s.client.Publish(ctx, "user:events", eventJSON)

	log.Printf("REDIS-USER-SVC: User deleted: %s", userID)
	return nil
}

func (s *RedisUserService) GetAllUsers(ctx context.Context) ([]string, error) {
	return s.client.SMembers(ctx, "users:all").Result()
}

func (s *RedisUserService) Close() error {
	return s.client.Close()
}

func (s *RedisUserService) GetClient() *redis.Client {
    return s.client
}

// ========== REDIS PAYMENT SERVICE ==========

type RedisPaymentService struct {
	client  *redis.Client
	pubsub  *redis.PubSub
	running bool
	stopChan chan struct{}
	mu      sync.RWMutex
}

func NewRedisPaymentService(addr string) *RedisPaymentService {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: "",
		DB:       0,
	})

	return &RedisPaymentService{
		client:   client,
		stopChan: make(chan struct{}),
	}
}

func (s *RedisPaymentService) StartListening(ctx context.Context) error {
	log.Printf("REDIS-PAYMENT-SVC: Started listening for events")
	s.running = true

	s.pubsub = s.client.Subscribe(ctx, "user:events")
	defer s.pubsub.Close()

	ch := s.pubsub.Channel()

	for {
		select {
		case <-s.stopChan:
			log.Printf("REDIS-PAYMENT-SVC: Stopping listener")
			return nil
		case <-ctx.Done():
			return ctx.Err()
		case msg, ok := <-ch:
			if !ok {
				return nil
			}

			var event RedisEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				log.Printf("REDIS-PAYMENT-SVC: Error unmarshaling event: %v", err)
				continue
			}

			if event.Type == "USER_CREATED" {
				var user RedisUser
				if err := json.Unmarshal([]byte(event.Data), &user); err != nil {
					log.Printf("REDIS-PAYMENT-SVC: Error unmarshaling user: %v", err)
					continue
				}

				log.Printf("REDIS-PAYMENT-SVC: Received USER_CREATED event for %s", user.ID)
				if err := s.ProcessPayment(ctx, user.ID, 99.99); err != nil {
					log.Printf("REDIS-PAYMENT-SVC: Error processing payment: %v", err)
				}
			}
		}
	}
}

func (s *RedisPaymentService) ProcessPayment(ctx context.Context, userID string, amount float64) error {
	log.Printf("REDIS-PAYMENT-SVC: Processing payment of %.2f for user %s", amount, userID)

	payment := &RedisPayment{
		Success:       true,
		TransactionID: fmt.Sprintf("redis-txn-%d", time.Now().Unix()),
		UserID:        userID,
		Amount:        amount,
		Timestamp:     time.Now(),
	}

	// Store payment
	paymentKey := fmt.Sprintf("payment:%s", payment.TransactionID)
	paymentMap := map[string]interface{}{
		"success":        payment.Success,
		"transaction_id": payment.TransactionID,
		"user_id":        payment.UserID,
		"amount":         payment.Amount,
		"timestamp":      payment.Timestamp.Format(time.RFC3339),
	}

	if err := s.client.HSet(ctx, paymentKey, paymentMap).Err(); err != nil {
		return err
	}

	// Add to user's payment history
	paymentJSON, _ := json.Marshal(payment)
	if err := s.client.LPush(ctx, fmt.Sprintf("payments:%s", userID), paymentJSON).Err(); err != nil {
		return err
	}

	// Update statistics
	pipe := s.client.Pipeline()
	pipe.HIncrBy(ctx, "stats:payments", "total", 1)
	if payment.Success {
		pipe.HIncrBy(ctx, "stats:payments", "success", 1)
	}
	if _, err := pipe.Exec(ctx); err != nil {
		return err
	}

	// Publish payment event
	event := RedisEvent{
		Type:      "PAYMENT_PROCESSED",
		UserID:    userID,
		Timestamp: time.Now(),
		Data:      string(paymentJSON),
	}

	eventJSON, _ := json.Marshal(event)
	s.client.Publish(ctx, "payment:events", eventJSON)

	log.Printf("REDIS-PAYMENT-SVC: Payment processed: %s", payment.TransactionID)
	return nil
}

func (s *RedisPaymentService) GetUserPayments(ctx context.Context, userID string, limit int64) ([]*RedisPayment, error) {
	paymentKey := fmt.Sprintf("payments:%s", userID)
	results, err := s.client.LRange(ctx, paymentKey, 0, limit-1).Result()
	if err != nil {
		return nil, err
	}

	payments := make([]*RedisPayment, 0, len(results))
	for _, result := range results {
		var payment RedisPayment
		if err := json.Unmarshal([]byte(result), &payment); err != nil {
			continue
		}
		payments = append(payments, &payment)
	}

	return payments, nil
}

func (s *RedisPaymentService) GetPaymentStats(ctx context.Context) (map[string]int64, error) {
	result, err := s.client.HGetAll(ctx, "stats:payments").Result()
	if err != nil {
		return nil, err
	}

	stats := make(map[string]int64)
	for k, v := range result {
		var val int64
		fmt.Sscanf(v, "%d", &val)
		stats[k] = val
	}

	return stats, nil
}

func (s *RedisPaymentService) Stop() {
	if s.running {
		close(s.stopChan)
		s.running = false
	}
}

func (s *RedisPaymentService) Close() error {
	s.Stop()
	if s.pubsub != nil {
		s.pubsub.Close()
	}
	return s.client.Close()
}

// ========== REDIS CACHE SERVICE ==========

type RedisCacheService struct {
	client *redis.Client
}

func NewRedisCacheService(addr string) *RedisCacheService {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: "",
		DB:       1, // Use different DB for cache
	})

	return &RedisCacheService{
		client: client,
	}
}

func (s *RedisCacheService) SetCache(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	cacheKey := fmt.Sprintf("cache:%s", key)

	var data string
	switch v := value.(type) {
	case string:
		data = v
	default:
		jsonData, err := json.Marshal(value)
		if err != nil {
			return err
		}
		data = string(jsonData)
	}

	return s.client.SetEx(ctx, cacheKey, data, ttl).Err()
}

func (s *RedisCacheService) GetCache(ctx context.Context, key string) (string, error) {
	cacheKey := fmt.Sprintf("cache:%s", key)
	return s.client.Get(ctx, cacheKey).Result()
}

func (s *RedisCacheService) DeleteCache(ctx context.Context, key string) error {
	cacheKey := fmt.Sprintf("cache:%s", key)
	return s.client.Del(ctx, cacheKey).Err()
}

func (s *RedisCacheService) InvalidatePattern(ctx context.Context, pattern string) (int64, error) {
	cachePattern := fmt.Sprintf("cache:%s", pattern)
	
	var cursor uint64
	var deletedCount int64

	for {
		keys, nextCursor, err := s.client.Scan(ctx, cursor, cachePattern, 100).Result()
		if err != nil {
			return deletedCount, err
		}

		if len(keys) > 0 {
			deleted, err := s.client.Del(ctx, keys...).Result()
			if err != nil {
				return deletedCount, err
			}
			deletedCount += deleted
		}

		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}

	return deletedCount, nil
}

func (s *RedisCacheService) Close() error {
	return s.client.Close()
}

// ========== REDIS BUSINESS SERVICE ==========

type RedisBusinessService struct {
	userService  *RedisUserService
	cacheService *RedisCacheService
	client       *redis.Client
	pubsub       *redis.PubSub
	results      map[string]*RedisPayment
	mu           sync.RWMutex
	running      bool
	stopChan     chan struct{}
}

func NewRedisBusinessService(addr string, userService *RedisUserService, cacheService *RedisCacheService) *RedisBusinessService {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: "",
		DB:       0,
	})

	return &RedisBusinessService{
		userService:  userService,
		cacheService: cacheService,
		client:       client,
		results:      make(map[string]*RedisPayment),
		stopChan:     make(chan struct{}),
	}
}

func (s *RedisBusinessService) StartListening(ctx context.Context) error {
	log.Printf("REDIS-BIZ: Started listening for business events")
	s.running = true

	s.pubsub = s.client.Subscribe(ctx, "user:events", "payment:events")
	defer s.pubsub.Close()

	ch := s.pubsub.Channel()

	for {
		select {
		case <-s.stopChan:
			return nil
		case <-ctx.Done():
			return ctx.Err()
		case msg, ok := <-ch:
			if !ok {
				return nil
			}

			var event RedisEvent
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				continue
			}

			if event.Type == "USER_CREATED" {
				log.Printf("REDIS-BIZ: User onboarding initiated for %s", event.UserID)
			}

			if event.Type == "PAYMENT_PROCESSED" {
				var payment RedisPayment
				if err := json.Unmarshal([]byte(event.Data), &payment); err != nil {
					continue
				}

				s.mu.Lock()
				s.results[payment.UserID] = &payment
				s.mu.Unlock()

				log.Printf("REDIS-BIZ: Payment flow completed for user %s - SUCCESS", payment.UserID)
			}
		}
	}
}

func (s *RedisBusinessService) CreateUserWithCache(ctx context.Context, name, email string) (*RedisUser, error) {
	user, err := s.userService.CreateUser(ctx, name, email)
	if err != nil {
		return nil, err
	}

	// Cache user data
	userJSON, _ := json.Marshal(user)
	s.cacheService.SetCache(ctx, fmt.Sprintf("user:%s", user.ID), string(userJSON), 30*time.Minute)

	return user, nil
}

func (s *RedisBusinessService) GetUserWithCache(ctx context.Context, userID string) (*RedisUser, error) {
	// Try cache first
	cached, err := s.cacheService.GetCache(ctx, fmt.Sprintf("user:%s", userID))
	if err == nil {
		var user RedisUser
		if err := json.Unmarshal([]byte(cached), &user); err == nil {
			log.Printf("REDIS-BIZ: Cache hit for user %s", userID)
			return &user, nil
		}
	}

	// Fallback to database
	user, err := s.userService.GetUser(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Cache for next time
	userJSON, _ := json.Marshal(user)
	s.cacheService.SetCache(ctx, fmt.Sprintf("user:%s", userID), string(userJSON), 30*time.Minute)

	log.Printf("REDIS-BIZ: Cache miss for user %s, cached now", userID)
	return user, nil
}

func (s *RedisBusinessService) UpdateUserAndInvalidateCache(ctx context.Context, userID, name, email string) error {
	if err := s.userService.UpdateUser(ctx, userID, name, email); err != nil {
		return err
	}

	// Invalidate cache
	return s.cacheService.DeleteCache(ctx, fmt.Sprintf("user:%s", userID))
}

func (s *RedisBusinessService) GetPaymentResult(userID string) (*RedisPayment, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	payment, exists := s.results[userID]
	return payment, exists
}

func (s *RedisBusinessService) Stop() {
	if s.running {
		close(s.stopChan)
		s.running = false
	}
}

func (s *RedisBusinessService) Close() error {
	s.Stop()
	if s.pubsub != nil {
		s.pubsub.Close()
	}
	return s.client.Close()
}

// ========== REDIS DISTRIBUTED LOCK ==========

type RedisDistributedLock struct {
	client *redis.Client
	key    string
	value  string
	ttl    time.Duration
}

func NewRedisDistributedLock(client *redis.Client, key string, ttl time.Duration) *RedisDistributedLock {
	return &RedisDistributedLock{
		client: client,
		key:    fmt.Sprintf("lock:%s", key),
		value:  fmt.Sprintf("%d", time.Now().UnixNano()),
		ttl:    ttl,
	}
}

func (l *RedisDistributedLock) Acquire(ctx context.Context) (bool, error) {
	return l.client.SetNX(ctx, l.key, l.value, l.ttl).Result()
}

func (l *RedisDistributedLock) Release(ctx context.Context) error {
	script := `
		if redis.call("get", KEYS[1]) == ARGV[1] then
			return redis.call("del", KEYS[1])
		else
			return 0
		end
	`
	return l.client.Eval(ctx, script, []string{l.key}, l.value).Err()
}