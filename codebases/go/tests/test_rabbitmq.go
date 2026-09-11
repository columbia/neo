package tests

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

// ========== RABBITMQ CONFIGURATION ==========

const (
	ExchangeUserEvents    = "rabbitmq.user.events"
	ExchangePaymentEvents = "rabbitmq.payment.events"

	QueueUserCreated         = "rabbitmq.user.created.queue"
	QueuePaymentProcessing   = "rabbitmq.payment.processing.queue"
	QueuePaymentCompleted    = "rabbitmq.payment.completed.queue"
	QueueBusinessNotifications = "rabbitmq.business.notifications.queue"

	RoutingKeyUserCreated      = "rabbitmq.user.created"
	RoutingKeyUserUpdated      = "rabbitmq.user.updated"
	RoutingKeyPaymentRequested = "rabbitmq.payment.requested"
	RoutingKeyPaymentProcessed = "rabbitmq.payment.processed"
)

// ========== DATA MODELS ==========

type RabbitMQUser struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	Timestamp time.Time `json:"timestamp"`
}

type RabbitMQPayment struct {
	Success       bool      `json:"success"`
	TransactionID string    `json:"transaction_id"`
	UserID        string    `json:"user_id"`
	Amount        float64   `json:"amount"`
	Timestamp     time.Time `json:"timestamp"`
}

type RabbitMQEvent struct {
	EventType string          `json:"event_type"`
	UserID    string          `json:"user_id,omitempty"`
	Timestamp time.Time       `json:"timestamp"`
	Data      json.RawMessage `json:"data"`
}

// ========== RABBITMQ BASE CONNECTION ==========

type RabbitMQConnection struct {
	conn    *amqp.Connection
	channel *amqp.Channel
	mu      sync.RWMutex
}

func NewRabbitMQConnection(url string) (*RabbitMQConnection, error) {
	conn, err := amqp.Dial(url)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	channel, err := conn.Channel()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to open channel: %w", err)
	}

	return &RabbitMQConnection{
		conn:    conn,
		channel: channel,
	}, nil
}

func (c *RabbitMQConnection) DeclareExchange(name, kind string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	return c.channel.ExchangeDeclare(
		name,
		kind,
		true,  // durable
		false, // auto-deleted
		false, // internal
		false, // no-wait
		nil,   // arguments
	)
}

func (c *RabbitMQConnection) DeclareQueue(name string) (amqp.Queue, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	return c.channel.QueueDeclare(
		name,
		true,  // durable
		false, // delete when unused
		false, // exclusive
		false, // no-wait
		nil,   // arguments
	)
}

func (c *RabbitMQConnection) BindQueue(queueName, exchangeName, routingKey string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	return c.channel.QueueBind(
		queueName,
		routingKey,
		exchangeName,
		false, // no-wait
		nil,   // arguments
	)
}

func (c *RabbitMQConnection) Publish(exchange, routingKey string, body []byte) error {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.channel.PublishWithContext(
		context.Background(),
		exchange,
		routingKey,
		false, // mandatory
		false, // immediate
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Timestamp:    time.Now(),
			Body:         body,
		},
	)
}

func (c *RabbitMQConnection) Consume(queueName string) (<-chan amqp.Delivery, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	return c.channel.Consume(
		queueName,
		"",    // consumer
		false, // auto-ack
		false, // exclusive
		false, // no-local
		false, // no-wait
		nil,   // args
	)
}

func (c *RabbitMQConnection) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.channel != nil {
		c.channel.Close()
	}
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// ========== RABBITMQ USER SERVICE (PUBLISHER) ==========

type RabbitMQUserService struct {
	conn   *RabbitMQConnection
	userDB map[string]*RabbitMQUser
	mu     sync.RWMutex
}

func NewRabbitMQUserService(url string) (*RabbitMQUserService, error) {
	conn, err := NewRabbitMQConnection(url)
	if err != nil {
		return nil, err
	}

	// Declare exchange
	if err := conn.DeclareExchange(ExchangeUserEvents, "topic"); err != nil {
		conn.Close()
		return nil, err
	}

	// Declare queue
	if _, err := conn.DeclareQueue(QueueUserCreated); err != nil {
		conn.Close()
		return nil, err
	}

	return &RabbitMQUserService{
		conn:   conn,
		userDB: make(map[string]*RabbitMQUser),
	}, nil
}

func (s *RabbitMQUserService) CreateUser(name, email string) (*RabbitMQUser, error) {
	log.Printf("RABBITMQ-USER-SVC: Creating user %s", name)

	user := &RabbitMQUser{
		ID:        fmt.Sprintf("rabbitmq-user-%d", time.Now().Unix()),
		Name:      name,
		Email:     email,
		Timestamp: time.Now(),
	}

	s.mu.Lock()
	s.userDB[user.ID] = user
	s.mu.Unlock()

	// Publish user created event
	if err := s.publishUserEvent("RABBITMQ_USER_CREATED", user); err != nil {
		return nil, err
	}

	log.Printf("RABBITMQ-USER-SVC: Published USER_CREATED event for %s", user.ID)
	return user, nil
}

func (s *RabbitMQUserService) GetUser(userID string) (*RabbitMQUser, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	user, exists := s.userDB[userID]
	if !exists {
		return nil, fmt.Errorf("user not found")
	}

	return user, nil
}

func (s *RabbitMQUserService) UpdateUser(userID, name, email string) (*RabbitMQUser, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	user, exists := s.userDB[userID]
	if !exists {
		return nil, fmt.Errorf("user not found")
	}

	user.Name = name
	user.Email = email
	user.Timestamp = time.Now()

	if err := s.publishUserEvent("RABBITMQ_USER_UPDATED", user); err != nil {
		return nil, err
	}

	log.Printf("RABBITMQ-USER-SVC: Published USER_UPDATED event for %s", user.ID)
	return user, nil
}

func (s *RabbitMQUserService) publishUserEvent(eventType string, user *RabbitMQUser) error {
	userData, err := json.Marshal(user)
	if err != nil {
		return err
	}

	event := RabbitMQEvent{
		EventType: eventType,
		UserID:    user.ID,
		Timestamp: time.Now(),
		Data:      userData,
	}

	eventJSON, err := json.Marshal(event)
	if err != nil {
		return err
	}

	return s.conn.Publish(ExchangeUserEvents, RoutingKeyUserCreated, eventJSON)
}

func (s *RabbitMQUserService) Close() error {
	return s.conn.Close()
}

// ========== RABBITMQ PAYMENT SERVICE (CONSUMER & PUBLISHER) ==========

type RabbitMQPaymentService struct {
	conn     *RabbitMQConnection
	payments map[string]*RabbitMQPayment
	mu       sync.RWMutex
	running  bool
	stopChan chan struct{}
}

func NewRabbitMQPaymentService(url string) (*RabbitMQPaymentService, error) {
	conn, err := NewRabbitMQConnection(url)
	if err != nil {
		return nil, err
	}

	// Declare exchanges
	if err := conn.DeclareExchange(ExchangeUserEvents, "topic"); err != nil {
		conn.Close()
		return nil, err
	}

	if err := conn.DeclareExchange(ExchangePaymentEvents, "topic"); err != nil {
		conn.Close()
		return nil, err
	}

	// Declare queues
	if _, err := conn.DeclareQueue(QueuePaymentProcessing); err != nil {
		conn.Close()
		return nil, err
	}

	if _, err := conn.DeclareQueue(QueuePaymentCompleted); err != nil {
		conn.Close()
		return nil, err
	}

	// Bind payment processing queue to user events
	if err := conn.BindQueue(QueuePaymentProcessing, ExchangeUserEvents, RoutingKeyUserCreated); err != nil {
		conn.Close()
		return nil, err
	}

	return &RabbitMQPaymentService{
		conn:     conn,
		payments: make(map[string]*RabbitMQPayment),
		stopChan: make(chan struct{}),
	}, nil
}

func (s *RabbitMQPaymentService) StartListening() error {
	log.Printf("RABBITMQ-PAYMENT-SVC: Started listening for events")
	s.running = true

	msgs, err := s.conn.Consume(QueuePaymentProcessing)
	if err != nil {
		return err
	}

	go func() {
		for {
			select {
			case <-s.stopChan:
				log.Printf("RABBITMQ-PAYMENT-SVC: Stopping listener")
				return
			case msg, ok := <-msgs:
				if !ok {
					log.Printf("RABBITMQ-PAYMENT-SVC: Message channel closed")
					return
				}

				if err := s.handleMessage(msg); err != nil {
					log.Printf("RABBITMQ-PAYMENT-SVC: Error handling message: %v", err)
					msg.Nack(false, true) // Requeue on error
				} else {
					msg.Ack(false)
				}
			}
		}
	}()

	return nil
}

func (s *RabbitMQPaymentService) handleMessage(msg amqp.Delivery) error {
	var event RabbitMQEvent
	if err := json.Unmarshal(msg.Body, &event); err != nil {
		return fmt.Errorf("failed to unmarshal event: %w", err)
	}

	log.Printf("RABBITMQ-PAYMENT-SVC: Received event: %s for user %s", event.EventType, event.UserID)

	if event.EventType == "RABBITMQ_USER_CREATED" {
		var user RabbitMQUser
		if err := json.Unmarshal(event.Data, &user); err != nil {
			return err
		}

		// Auto-trigger payment for new users
		return s.ProcessPayment(user.ID, 99.99)
	}

	return nil
}

func (s *RabbitMQPaymentService) ProcessPayment(userID string, amount float64) error {
	log.Printf("RABBITMQ-PAYMENT-SVC: Processing payment of %.2f for user %s", amount, userID)

	payment := &RabbitMQPayment{
		Success:       true,
		TransactionID: fmt.Sprintf("rabbitmq-txn-%d", time.Now().Unix()),
		UserID:        userID,
		Amount:        amount,
		Timestamp:     time.Now(),
	}

	s.mu.Lock()
	s.payments[payment.TransactionID] = payment
	s.mu.Unlock()

	// Publish payment processed event
	return s.publishPaymentEvent("RABBITMQ_PAYMENT_PROCESSED", payment)
}

func (s *RabbitMQPaymentService) publishPaymentEvent(eventType string, payment *RabbitMQPayment) error {
	paymentData, err := json.Marshal(payment)
	if err != nil {
		return err
	}

	event := RabbitMQEvent{
		EventType: eventType,
		UserID:    payment.UserID,
		Timestamp: time.Now(),
		Data:      paymentData,
	}

	eventJSON, err := json.Marshal(event)
	if err != nil {
		return err
	}

	if err := s.conn.Publish(ExchangePaymentEvents, RoutingKeyPaymentProcessed, eventJSON); err != nil {
		return err
	}

	log.Printf("RABBITMQ-PAYMENT-SVC: Published PAYMENT_PROCESSED event: %s", payment.TransactionID)
	return nil
}

func (s *RabbitMQPaymentService) Stop() {
	if s.running {
		close(s.stopChan)
		s.running = false
	}
}

func (s *RabbitMQPaymentService) Close() error {
	s.Stop()
	return s.conn.Close()
}

// ========== RABBITMQ BUSINESS SERVICE (CONSUMER & ORCHESTRATOR) ==========

type RabbitMQBusinessService struct {
	conn           *RabbitMQConnection
	userService    *RabbitMQUserService
	paymentResults map[string]*RabbitMQPayment
	mu             sync.RWMutex
	running        bool
	stopChan       chan struct{}
}

func NewRabbitMQBusinessService(url string, userService *RabbitMQUserService) (*RabbitMQBusinessService, error) {
	conn, err := NewRabbitMQConnection(url)
	if err != nil {
		return nil, err
	}

	// Declare exchange and queue
	if err := conn.DeclareExchange(ExchangeUserEvents, "topic"); err != nil {
		conn.Close()
		return nil, err
	}

	if err := conn.DeclareExchange(ExchangePaymentEvents, "topic"); err != nil {
		conn.Close()
		return nil, err
	}

	if _, err := conn.DeclareQueue(QueueBusinessNotifications); err != nil {
		conn.Close()
		return nil, err
	}

	// Bind to both user and payment events
	if err := conn.BindQueue(QueueBusinessNotifications, ExchangeUserEvents, "rabbitmq.user.*"); err != nil {
		conn.Close()
		return nil, err
	}

	if err := conn.BindQueue(QueueBusinessNotifications, ExchangePaymentEvents, "rabbitmq.payment.*"); err != nil {
		conn.Close()
		return nil, err
	}

	return &RabbitMQBusinessService{
		conn:           conn,
		userService:    userService,
		paymentResults: make(map[string]*RabbitMQPayment),
		stopChan:       make(chan struct{}),
	}, nil
}

func (s *RabbitMQBusinessService) StartListening() error {
	log.Printf("RABBITMQ-BIZ: Started listening for business events")
	s.running = true

	msgs, err := s.conn.Consume(QueueBusinessNotifications)
	if err != nil {
		return err
	}

	go func() {
		for {
			select {
			case <-s.stopChan:
				return
			case msg, ok := <-msgs:
				if !ok {
					return
				}

				var event RabbitMQEvent
				if err := json.Unmarshal(msg.Body, &event); err != nil {
					log.Printf("RABBITMQ-BIZ: Error unmarshaling: %v", err)
					msg.Nack(false, false)
					continue
				}

				if event.EventType == "RABBITMQ_USER_CREATED" {
					log.Printf("RABBITMQ-BIZ: User onboarding initiated for %s", event.UserID)
				}

				if event.EventType == "RABBITMQ_PAYMENT_PROCESSED" {
					var payment RabbitMQPayment
					if err := json.Unmarshal(event.Data, &payment); err != nil {
						log.Printf("RABBITMQ-BIZ: Error unmarshaling payment: %v", err)
						msg.Nack(false, false)
						continue
					}

					s.mu.Lock()
					s.paymentResults[payment.UserID] = &payment
					s.mu.Unlock()

					log.Printf("RABBITMQ-BIZ: Payment flow completed for user %s - Result: SUCCESS", payment.UserID)
				}

				msg.Ack(false)
			}
		}
	}()

	return nil
}

func (s *RabbitMQBusinessService) OnboardUserAndMakePayment(name, email string) (*RabbitMQUser, error) {
	log.Printf("\nRABBITMQ-BIZ: Starting user onboarding flow for %s", name)

	user, err := s.userService.CreateUser(name, email)
	if err != nil {
		return nil, err
	}

	log.Printf("RABBITMQ-BIZ: User creation initiated for %s", user.ID)
	return user, nil
}

func (s *RabbitMQBusinessService) GetPaymentResult(userID string) (*RabbitMQPayment, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	payment, exists := s.paymentResults[userID]
	return payment, exists
}

func (s *RabbitMQBusinessService) Stop() {
	if s.running {
		close(s.stopChan)
		s.running = false
	}
}

func (s *RabbitMQBusinessService) Close() error {
	s.Stop()
	return s.conn.Close()
}

// ========== RABBITMQ RPC PATTERN ==========

type RabbitMQRPCClient struct {
	conn         *RabbitMQConnection
	replyQueue   amqp.Queue
	pendingCalls map[string]chan []byte
	mu           sync.RWMutex
}

func NewRabbitMQRPCClient(url string) (*RabbitMQRPCClient, error) {
	conn, err := NewRabbitMQConnection(url)
	if err != nil {
		return nil, err
	}

	// Declare exclusive reply queue
	replyQueue, err := conn.channel.QueueDeclare(
		"",    // name
		false, // durable
		true,  // delete when unused
		true,  // exclusive
		false, // no-wait
		nil,   // arguments
	)
	if err != nil {
		conn.Close()
		return nil, err
	}

	client := &RabbitMQRPCClient{
		conn:         conn,
		replyQueue:   replyQueue,
		pendingCalls: make(map[string]chan []byte),
	}

	// Start consuming replies
	go client.consumeReplies()

	return client, nil
}

func (c *RabbitMQRPCClient) consumeReplies() {
	msgs, err := c.conn.Consume(c.replyQueue.Name)
	if err != nil {
		log.Printf("RABBITMQ-RPC: Error consuming replies: %v", err)
		return
	}

	for msg := range msgs {
		c.mu.RLock()
		replyChan, exists := c.pendingCalls[msg.CorrelationId]
		c.mu.RUnlock()

		if exists {
			replyChan <- msg.Body
			msg.Ack(false)
		}
	}
}

func (c *RabbitMQRPCClient) Call(queueName string, request []byte, timeout time.Duration) ([]byte, error) {
	correlationID := fmt.Sprintf("%d", time.Now().UnixNano())
	replyChan := make(chan []byte, 1)

	c.mu.Lock()
	c.pendingCalls[correlationID] = replyChan
	c.mu.Unlock()

	defer func() {
		c.mu.Lock()
		delete(c.pendingCalls, correlationID)
		c.mu.Unlock()
	}()

	err := c.conn.channel.PublishWithContext(
		context.Background(),
		"",        // exchange
		queueName, // routing key
		false,     // mandatory
		false,     // immediate
		amqp.Publishing{
			ContentType:   "application/json",
			CorrelationId: correlationID,
			ReplyTo:       c.replyQueue.Name,
			Body:          request,
		},
	)
	if err != nil {
		return nil, err
	}

	select {
	case reply := <-replyChan:
		return reply, nil
	case <-time.After(timeout):
		return nil, fmt.Errorf("RPC call timeout")
	}
}

func (c *RabbitMQRPCClient) Close() error {
	return c.conn.Close()
}