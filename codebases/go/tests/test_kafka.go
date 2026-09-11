package tests

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"sync"
	"time"

	"github.com/segmentio/kafka-go"
)

// ========== KAFKA EVENT TYPES ==========

const (
	EventUserCreated          = "user.created"
	EventUserUpdated          = "user.updated"
	EventUserDeleted          = "user.deleted"
	EventPaymentRequested     = "payment.requested"
	EventPaymentProcessed     = "payment.processed"
	EventPaymentFailed        = "payment.failed"
	EventNotificationSent     = "notification.sent"
)

const (
	TopicUserEvents       = "user-events"
	TopicPaymentEvents    = "payment-events"
	TopicNotificationEvents = "notification-events"
)

// ========== DATA MODELS ==========

type KafkaUser struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	Timestamp time.Time `json:"timestamp"`
}

type KafkaPayment struct {
	Success       bool      `json:"success"`
	TransactionID string    `json:"transaction_id"`
	UserID        string    `json:"user_id"`
	Amount        float64   `json:"amount"`
	Timestamp     time.Time `json:"timestamp"`
}

type KafkaEvent struct {
	EventType string          `json:"event_type"`
	UserID    string          `json:"user_id,omitempty"`
	Timestamp time.Time       `json:"timestamp"`
	Data      json.RawMessage `json:"data"`
}

// ========== KAFKA USER SERVICE (PRODUCER) ==========

type KafkaUserService struct {
	writer   *kafka.Writer
	userDB   map[string]*KafkaUser
	mu       sync.RWMutex
	brokers  []string
}

func NewKafkaUserService(brokers []string) *KafkaUserService {
	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        TopicUserEvents,
		Balancer:     &kafka.LeastBytes{},
		RequiredAcks: kafka.RequireAll,
		MaxAttempts:  3,
		Compression:  kafka.Snappy,
	}

	return &KafkaUserService{
		writer:  writer,
		userDB:  make(map[string]*KafkaUser),
		brokers: brokers,
	}
}

func (s *KafkaUserService) CreateUser(ctx context.Context, name, email string) (*KafkaUser, error) {
	log.Printf("KAFKA-USER-SVC: Creating user %s", name)

	user := &KafkaUser{
		ID:        fmt.Sprintf("kafka-user-%d", time.Now().Unix()),
		Name:      name,
		Email:     email,
		Timestamp: time.Now(),
	}

	s.mu.Lock()
	s.userDB[user.ID] = user
	s.mu.Unlock()

	// Publish user created event
	if err := s.publishUserEvent(ctx, EventUserCreated, user); err != nil {
		return nil, fmt.Errorf("failed to publish event: %w", err)
	}

	log.Printf("KAFKA-USER-SVC: Published USER_CREATED event for %s", user.ID)
	return user, nil
}

func (s *KafkaUserService) UpdateUser(ctx context.Context, userID, name, email string) (*KafkaUser, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, exists := s.userDB[userID]
	if !exists {
		return nil, fmt.Errorf("user not found")
	}

	user.Name = name
	user.Email = email
	user.Timestamp = time.Now()

	// Publish user updated event
	if err := s.publishUserEvent(ctx, EventUserUpdated, user); err != nil {
		return nil, err
	}

	log.Printf("KAFKA-USER-SVC: Published USER_UPDATED event for %s", user.ID)
	return user, nil
}

func (s *KafkaUserService) DeleteUser(ctx context.Context, userID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, exists := s.userDB[userID]
	if !exists {
		return fmt.Errorf("user not found")
	}

	delete(s.userDB, userID)

	// Publish user deleted event
	if err := s.publishUserEvent(ctx, EventUserDeleted, user); err != nil {
		return err
	}

	log.Printf("KAFKA-USER-SVC: Published USER_DELETED event for %s", userID)
	return nil
}

func (s *KafkaUserService) publishUserEvent(ctx context.Context, eventType string, user *KafkaUser) error {
	userData, err := json.Marshal(user)
	if err != nil {
		return err
	}

	event := KafkaEvent{
		EventType: eventType,
		UserID:    user.ID,
		Timestamp: time.Now(),
		Data:      userData,
	}

	eventJSON, err := json.Marshal(event)
	if err != nil {
		return err
	}

	message := kafka.Message{
		Key:   []byte(user.ID),
		Value: eventJSON,
		Headers: []kafka.Header{
			{Key: "event-type", Value: []byte(eventType)},
			{Key: "timestamp", Value: []byte(time.Now().Format(time.RFC3339))},
		},
	}

	return s.writer.WriteMessages(ctx, message)
}

func (s *KafkaUserService) Close() error {
	return s.writer.Close()
}

// ========== KAFKA PAYMENT SERVICE (CONSUMER & PRODUCER) ==========

type KafkaPaymentService struct {
	reader   *kafka.Reader
	writer   *kafka.Writer
	payments map[string]*KafkaPayment
	mu       sync.RWMutex
	brokers  []string
	running  bool
}

func NewKafkaPaymentService(brokers []string, groupID string) *KafkaPaymentService {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          TopicUserEvents,
		GroupID:        groupID,
		MinBytes:       10e3, // 10KB
		MaxBytes:       10e6, // 10MB
		CommitInterval: time.Second,
		StartOffset:    kafka.LastOffset,
	})

	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        TopicPaymentEvents,
		Balancer:     &kafka.LeastBytes{},
		RequiredAcks: kafka.RequireAll,
		MaxAttempts:  3,
		Compression:  kafka.Snappy,
	}

	return &KafkaPaymentService{
		reader:   reader,
		writer:   writer,
		payments: make(map[string]*KafkaPayment),
		brokers:  brokers,
	}
}

func (s *KafkaPaymentService) StartListening(ctx context.Context) error {
	log.Printf("KAFKA-PAYMENT-SVC: Started listening for events")
	s.running = true

	for s.running {
		select {
		case <-ctx.Done():
			log.Printf("KAFKA-PAYMENT-SVC: Context cancelled, stopping listener")
			return ctx.Err()
		default:
			message, err := s.reader.FetchMessage(ctx)
			if err != nil {
				if err == context.Canceled || err == context.DeadlineExceeded {
					return nil
				}
				log.Printf("KAFKA-PAYMENT-SVC: Error fetching message: %v", err)
				continue
			}

			if err := s.handleMessage(ctx, message); err != nil {
				log.Printf("KAFKA-PAYMENT-SVC: Error handling message: %v", err)
			}

			if err := s.reader.CommitMessages(ctx, message); err != nil {
				log.Printf("KAFKA-PAYMENT-SVC: Error committing message: %v", err)
			}
		}
	}

	return nil
}

func (s *KafkaPaymentService) handleMessage(ctx context.Context, message kafka.Message) error {
	var event KafkaEvent
	if err := json.Unmarshal(message.Value, &event); err != nil {
		return fmt.Errorf("failed to unmarshal event: %w", err)
	}

	log.Printf("KAFKA-PAYMENT-SVC: Received event: %s for user %s", event.EventType, event.UserID)

	if event.EventType == EventUserCreated {
		var user KafkaUser
		if err := json.Unmarshal(event.Data, &user); err != nil {
			return err
		}

		// Auto-trigger payment for new users
		return s.ProcessPayment(ctx, user.ID, 99.99)
	}

	return nil
}

func (s *KafkaPaymentService) ProcessPayment(ctx context.Context, userID string, amount float64) error {
	log.Printf("KAFKA-PAYMENT-SVC: Processing payment of %.2f for user %s", amount, userID)

	success := true // 100% success for testing
	payment := &KafkaPayment{
		Success:       success,
		TransactionID: fmt.Sprintf("kafka-txn-%d", time.Now().Unix()),
		UserID:        userID,
		Amount:        amount,
		Timestamp:     time.Now(),
	}

	s.mu.Lock()
	s.payments[payment.TransactionID] = payment
	s.mu.Unlock()

	// Publish payment processed event
	return s.publishPaymentEvent(ctx, EventPaymentProcessed, payment)
}

func (s *KafkaPaymentService) publishPaymentEvent(ctx context.Context, eventType string, payment *KafkaPayment) error {
	paymentData, err := json.Marshal(payment)
	if err != nil {
		return err
	}

	event := KafkaEvent{
		EventType: eventType,
		UserID:    payment.UserID,
		Timestamp: time.Now(),
		Data:      paymentData,
	}

	eventJSON, err := json.Marshal(event)
	if err != nil {
		return err
	}

	message := kafka.Message{
		Key:   []byte(payment.UserID),
		Value: eventJSON,
		Headers: []kafka.Header{
			{Key: "event-type", Value: []byte(eventType)},
			{Key: "transaction-id", Value: []byte(payment.TransactionID)},
		},
	}

	if err := s.writer.WriteMessages(ctx, message); err != nil {
		return err
	}

	log.Printf("KAFKA-PAYMENT-SVC: Published PAYMENT_PROCESSED event: %s", payment.TransactionID)
	return nil
}

func (s *KafkaPaymentService) Stop() {
	s.running = false
}

func (s *KafkaPaymentService) Close() error {
	s.Stop()
	if err := s.reader.Close(); err != nil {
		return err
	}
	return s.writer.Close()
}

// ========== KAFKA BUSINESS SERVICE (CONSUMER & ORCHESTRATOR) ==========

type KafkaBusinessService struct {
	userReader    *kafka.Reader
	paymentReader *kafka.Reader
	userService   *KafkaUserService
	results       map[string]*KafkaPayment
	mu            sync.RWMutex
	brokers       []string
	running       bool
}

func NewKafkaBusinessService(brokers []string, userService *KafkaUserService) *KafkaBusinessService {
	userReader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          TopicUserEvents,
		GroupID:        "business-service-users",
		MinBytes:       10e3,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
		StartOffset:    kafka.LastOffset,
	})

	paymentReader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          TopicPaymentEvents,
		GroupID:        "business-service-payments",
		MinBytes:       10e3,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
		StartOffset:    kafka.LastOffset,
	})

	return &KafkaBusinessService{
		userReader:    userReader,
		paymentReader: paymentReader,
		userService:   userService,
		results:       make(map[string]*KafkaPayment),
		brokers:       brokers,
	}
}

func (s *KafkaBusinessService) StartListening(ctx context.Context) error {
	log.Printf("KAFKA-BIZ: Started listening for business events")
	s.running = true

	var wg sync.WaitGroup
	errChan := make(chan error, 2)

	// Listen to user events
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := s.listenUserEvents(ctx); err != nil {
			errChan <- err
		}
	}()

	// Listen to payment events
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := s.listenPaymentEvents(ctx); err != nil {
			errChan <- err
		}
	}()

	wg.Wait()
	close(errChan)

	for err := range errChan {
		if err != nil {
			return err
		}
	}

	return nil
}

func (s *KafkaBusinessService) listenUserEvents(ctx context.Context) error {
	for s.running {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			message, err := s.userReader.FetchMessage(ctx)
			if err != nil {
				if err == context.Canceled || err == context.DeadlineExceeded {
					return nil
				}
				log.Printf("KAFKA-BIZ: Error fetching user message: %v", err)
				continue
			}

			var event KafkaEvent
			if err := json.Unmarshal(message.Value, &event); err != nil {
				log.Printf("KAFKA-BIZ: Error unmarshaling event: %v", err)
				continue
			}

			log.Printf("KAFKA-BIZ: User event received: %s for user %s", event.EventType, event.UserID)

			if err := s.userReader.CommitMessages(ctx, message); err != nil {
				log.Printf("KAFKA-BIZ: Error committing message: %v", err)
			}
		}
	}
	return nil
}

func (s *KafkaBusinessService) listenPaymentEvents(ctx context.Context) error {
	for s.running {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			message, err := s.paymentReader.FetchMessage(ctx)
			if err != nil {
				if err == context.Canceled || err == context.DeadlineExceeded {
					return nil
				}
				log.Printf("KAFKA-BIZ: Error fetching payment message: %v", err)
				continue
			}

			var event KafkaEvent
			if err := json.Unmarshal(message.Value, &event); err != nil {
				log.Printf("KAFKA-BIZ: Error unmarshaling event: %v", err)
				continue
			}

			if event.EventType == EventPaymentProcessed {
				var payment KafkaPayment
				if err := json.Unmarshal(event.Data, &payment); err != nil {
					log.Printf("KAFKA-BIZ: Error unmarshaling payment: %v", err)
					continue
				}

				s.mu.Lock()
				s.results[payment.UserID] = &payment
				s.mu.Unlock()

				log.Printf("KAFKA-BIZ: Payment flow completed for user %s - Transaction: %s", 
					payment.UserID, payment.TransactionID)
			}

			if err := s.paymentReader.CommitMessages(ctx, message); err != nil {
				log.Printf("KAFKA-BIZ: Error committing message: %v", err)
			}
		}
	}
	return nil
}

func (s *KafkaBusinessService) OnboardUserAndMakePayment(ctx context.Context, name, email string) (*KafkaUser, error) {
	log.Printf("\nKAFKA-BIZ: Starting user onboarding flow for %s", name)

	user, err := s.userService.CreateUser(ctx, name, email)
	if err != nil {
		return nil, err
	}

	log.Printf("KAFKA-BIZ: User creation initiated for %s", user.ID)
	return user, nil
}

func (s *KafkaBusinessService) GetPaymentResult(userID string) (*KafkaPayment, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	payment, exists := s.results[userID]
	return payment, exists
}

func (s *KafkaBusinessService) Stop() {
	s.running = false
}

func (s *KafkaBusinessService) Close() error {
	s.Stop()
	if err := s.userReader.Close(); err != nil {
		return err
	}
	return s.paymentReader.Close()
}

// ========== KAFKA PRODUCER WITH BATCH WRITES ==========

type KafkaBatchProducer struct {
	writer *kafka.Writer
}

func NewKafkaBatchProducer(brokers []string, topic string) *KafkaBatchProducer {
	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		MaxAttempts:  3,
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
	}

	return &KafkaBatchProducer{writer: writer}
}

func (p *KafkaBatchProducer) SendBatch(ctx context.Context, events []KafkaEvent) error {
	messages := make([]kafka.Message, len(events))

	for i, event := range events {
		eventJSON, err := json.Marshal(event)
		if err != nil {
			return err
		}

		messages[i] = kafka.Message{
			Key:   []byte(event.UserID),
			Value: eventJSON,
			Headers: []kafka.Header{
				{Key: "event-type", Value: []byte(event.EventType)},
			},
		}
	}

	return p.writer.WriteMessages(ctx, messages...)
}

func (p *KafkaBatchProducer) Close() error {
	return p.writer.Close()
}

// ========== KAFKA CONSUMER WITH MANUAL OFFSET CONTROL ==========

type KafkaManualConsumer struct {
	reader *kafka.Reader
}

func NewKafkaManualConsumer(brokers []string, topic, groupID string) *KafkaManualConsumer {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          topic,
		GroupID:        groupID,
		MinBytes:       10e3,
		MaxBytes:       10e6,
		CommitInterval: 0, // Manual commit
		StartOffset:    kafka.FirstOffset,
	})

	return &KafkaManualConsumer{reader: reader}
}

func (c *KafkaManualConsumer) ConsumeWithManualCommit(ctx context.Context, handler func(KafkaEvent) error) error {
	for {
		message, err := c.reader.FetchMessage(ctx)
		if err != nil {
			if err == context.Canceled || err == context.DeadlineExceeded {
				return nil
			}
			return err
		}

		var event KafkaEvent
		if err := json.Unmarshal(message.Value, &event); err != nil {
			log.Printf("Error unmarshaling event: %v", err)
			continue
		}

		if err := handler(event); err != nil {
			log.Printf("Error handling event: %v", err)
			continue
		}

		// Manual commit after successful processing
		if err := c.reader.CommitMessages(ctx, message); err != nil {
			log.Printf("Error committing message: %v", err)
		}
	}
}

func (c *KafkaManualConsumer) Close() error {
	return c.reader.Close()
}

// ========== KAFKA TOPIC ADMIN OPERATIONS ==========

func CreateKafkaTopics(brokers []string, topics []string) error {
	conn, err := kafka.Dial("tcp", brokers[0])
	if err != nil {
		return err
	}
	defer conn.Close()

	controller, err := conn.Controller()
	if err != nil {
		return err
	}

	controllerConn, err := kafka.Dial("tcp", net.JoinHostPort(controller.Host, fmt.Sprintf("%d", controller.Port)))
	if err != nil {
		return err
	}
	defer controllerConn.Close()

	topicConfigs := make([]kafka.TopicConfig, len(topics))
	for i, topic := range topics {
		topicConfigs[i] = kafka.TopicConfig{
			Topic:             topic,
			NumPartitions:     3,
			ReplicationFactor: 1,
		}
	}

	return controllerConn.CreateTopics(topicConfigs...)
}

// ========== KAFKA HEALTH CHECK ==========

func CheckKafkaHealth(brokers []string) error {
	conn, err := kafka.Dial("tcp", brokers[0])
	if err != nil {
		return fmt.Errorf("failed to connect to kafka: %w", err)
	}
	defer conn.Close()

	partitions, err := conn.ReadPartitions()
	if err != nil {
		return fmt.Errorf("failed to read partitions: %w", err)
	}

	log.Printf("KAFKA-HEALTH: Connected successfully, found %d partitions", len(partitions))
	return nil
}