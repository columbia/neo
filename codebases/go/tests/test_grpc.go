package tests

import (
	"context"
	"fmt"
	"io"
	"log"
	"sync"
	"time"
)

// ========== GRPC USER SERVICE IMPLEMENTATION ==========

type GRPCUserServiceImpl struct {
	UnimplementedUserServiceServer
	users map[string]*UserResponse
	mu    sync.RWMutex
}

func NewGRPCUserService() *GRPCUserServiceImpl {
	return &GRPCUserServiceImpl{
		users: make(map[string]*UserResponse),
	}
}

func (s *GRPCUserServiceImpl) GetUser(ctx context.Context, req *UserRequest) (*UserResponse, error) {
	log.Printf("GRPC-USER-SVC: GetUser called for %s", req.UserId)

	s.mu.RLock()
	user, exists := s.users[req.UserId]
	s.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("user %s not found", req.UserId)
	}

	return user, nil
}

func (s *GRPCUserServiceImpl) CreateUser(ctx context.Context, req *GRPCCreateUserRequest) (*UserResponse, error) {
	log.Printf("GRPC-USER-SVC: CreateUser called for %s", req.Name)

	userID := fmt.Sprintf("grpc-user-%d", len(s.users)+1)
	user := &UserResponse{
		Id:         userID,
		Name:       req.Name,
		Email:      req.Email,
	}

	s.mu.Lock()
	s.users[userID] = user
	s.mu.Unlock()

	return user, nil
}

func (s *GRPCUserServiceImpl) UpdateUser(ctx context.Context, req *UpdateUserRequest) (*UserResponse, error) {
	log.Printf("GRPC-USER-SVC: UpdateUser called for %s", req.UserId)

	s.mu.Lock()
	defer s.mu.Unlock()

	user, exists := s.users[req.UserId]
	if !exists {
		return nil, fmt.Errorf("user %s not found", req.UserId)
	}

	user.Name = req.Name
	user.Email = req.Email

	return user, nil
}

func (s *GRPCUserServiceImpl) DeleteUser(ctx context.Context, req *UserRequest) (*DeleteResponse, error) {
	log.Printf("GRPC-USER-SVC: DeleteUser called for %s", req.UserId)

	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.users[req.UserId]; !exists {
		return &DeleteResponse{Success: false, Message: "User not found"}, nil
	}

	delete(s.users, req.UserId)
	return &DeleteResponse{Success: true, Message: "User deleted successfully"}, nil
}

// Mock streaming implementation for ListUsers
type mockUserListStream struct {
	users []*UserResponse
	index int
}

func (s *mockUserListStream) Send(user *UserResponse) error {
	return nil
}

func (s *GRPCUserServiceImpl) ListUsers(req *ListUsersRequest, stream UserService_ListUsersServer) error {
	log.Printf("GRPC-USER-SVC: ListUsers called (server streaming)")

	s.mu.RLock()
	users := make([]*UserResponse, 0, len(s.users))
	for _, user := range s.users {
		users = append(users, user)
	}
	s.mu.RUnlock()

	for _, user := range users {
		if err := stream.Send(user); err != nil {
			return err
		}
		time.Sleep(100 * time.Millisecond)
	}

	return nil
}

// ========== GRPC PAYMENT SERVICE IMPLEMENTATION ==========

type GRPCPaymentServiceImpl struct {
	UnimplementedPaymentServiceServer
	payments map[string]*PaymentResponse
	mu       sync.RWMutex
}

func NewGRPCPaymentService() *GRPCPaymentServiceImpl {
	return &GRPCPaymentServiceImpl{
		payments: make(map[string]*PaymentResponse),
	}
}

func (s *GRPCPaymentServiceImpl) ProcessPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error) {
	log.Printf("GRPC-PAYMENT-SVC: ProcessPayment called for user %s, amount %.2f", req.UserId, req.Amount)

	txnID := fmt.Sprintf("grpc-txn-%d", time.Now().Unix())
	payment := &PaymentResponse{
		Success:       true,
		TransactionId: txnID,
		UserId:        req.UserId,
		Amount:        req.Amount,
		Status:        "completed",
		Message:       "Payment processed successfully",
	}

	s.mu.Lock()
	s.payments[txnID] = payment
	s.mu.Unlock()

	return payment, nil
}

func (s *GRPCPaymentServiceImpl) RefundPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error) {
	log.Printf("GRPC-PAYMENT-SVC: RefundPayment called for user %s, amount %.2f", req.UserId, req.Amount)

	txnID := fmt.Sprintf("grpc-refund-%d", time.Now().Unix())
	payment := &PaymentResponse{
		Success:       true,
		TransactionId: txnID,
		UserId:        req.UserId,
		Amount:        req.Amount,
		Status:        "refunded",
		Message:       "Refund processed successfully",
	}

	return payment, nil
}

func (s *GRPCPaymentServiceImpl) GetPaymentStatus(ctx context.Context, req *PaymentStatusRequest) (*PaymentResponse, error) {
	s.mu.RLock()
	payment, exists := s.payments[req.TransactionId]
	s.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("payment not found")
	}

	return payment, nil
}

// ========== GRPC NOTIFICATION SERVICE ==========

type GRPCNotificationServiceImpl struct {
	UnimplementedNotificationServiceServer
}

func NewGRPCNotificationService() *GRPCNotificationServiceImpl {
	return &GRPCNotificationServiceImpl{}
}

func (s *GRPCNotificationServiceImpl) SendNotification(ctx context.Context, req *NotificationRequest) (*NotificationResponse, error) {
	log.Printf("GRPC-NOTIF-SVC: SendNotification to user %s", req.UserId)

	return &NotificationResponse{
		Success:         true,
		Message:         "Notification sent",
		RecipientsCount: 1,
	}, nil
}

func (s *GRPCNotificationServiceImpl) BroadcastMessage(ctx context.Context, req *BroadcastRequest) (*NotificationResponse, error) {
	log.Printf("GRPC-NOTIF-SVC: BroadcastMessage to %d users", len(req.UserIds))

	return &NotificationResponse{
		Success:         true,
		Message:         "Broadcast sent",
		RecipientsCount: int32(len(req.UserIds)),
	}, nil
}

// ========== SIMPLE GRPC CLIENT (MOCK FOR TESTING) ==========

// SimpleUserClient is a mock client that doesn't need actual gRPC connections
type SimpleUserClient struct {
	service *GRPCUserServiceImpl
}

func NewSimpleUserClient() *SimpleUserClient {
	return &SimpleUserClient{
		service: NewGRPCUserService(),
	}
}

func (c *SimpleUserClient) GetUser(ctx context.Context, req *UserRequest) (*UserResponse, error) {
	return c.service.GetUser(ctx, req)
}

func (c *SimpleUserClient) CreateUser(ctx context.Context, req *GRPCCreateUserRequest) (*UserResponse, error) {
	return c.service.CreateUser(ctx, req)
}

func (c *SimpleUserClient) UpdateUser(ctx context.Context, req *UpdateUserRequest) (*UserResponse, error) {
	return c.service.UpdateUser(ctx, req)
}

func (c *SimpleUserClient) DeleteUser(ctx context.Context, req *UserRequest) (*DeleteResponse, error) {
	return c.service.DeleteUser(ctx, req)
}

func (c *SimpleUserClient) ListUsers(ctx context.Context, req *ListUsersRequest) (UserService_ListUsersClient, error) {
	c.service.mu.RLock()
	users := make([]*UserResponse, 0, len(c.service.users))
	for _, user := range c.service.users {
		users = append(users, user)
	}
	c.service.mu.RUnlock()

	return &mockListUsersClient{users: users}, nil
}

func (c *SimpleUserClient) StreamUserUpdates(ctx context.Context, req *UserRequest) (UserService_StreamUserUpdatesClient, error) {
	return nil, fmt.Errorf("not implemented")
}

// SimplePaymentClient is a mock client
type SimplePaymentClient struct {
	service *GRPCPaymentServiceImpl
}

func NewSimplePaymentClient() *SimplePaymentClient {
	return &SimplePaymentClient{
		service: NewGRPCPaymentService(),
	}
}

func (c *SimplePaymentClient) ProcessPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error) {
	return c.service.ProcessPayment(ctx, req)
}

func (c *SimplePaymentClient) RefundPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error) {
	return c.service.RefundPayment(ctx, req)
}

func (c *SimplePaymentClient) GetPaymentStatus(ctx context.Context, req *PaymentStatusRequest) (*PaymentResponse, error) {
	return c.service.GetPaymentStatus(ctx, req)
}

func (c *SimplePaymentClient) BatchProcessPayments(ctx context.Context) (PaymentService_BatchProcessPaymentsClient, error) {
	return &mockBatchPaymentsClient{}, nil
}

func (c *SimplePaymentClient) StreamPayments(ctx context.Context) (PaymentService_StreamPaymentsClient, error) {
	return &mockStreamPaymentsClient{
		sendChan: make(chan *PaymentRequest, 10),
		recvChan: make(chan *PaymentResponse, 10),
	}, nil
}

// SimpleNotificationClient is a mock client
type SimpleNotificationClient struct {
	service *GRPCNotificationServiceImpl
}

func NewSimpleNotificationClient() *SimpleNotificationClient {
	return &SimpleNotificationClient{
		service: NewGRPCNotificationService(),
	}
}

func (c *SimpleNotificationClient) SendNotification(ctx context.Context, req *NotificationRequest) (*NotificationResponse, error) {
	return c.service.SendNotification(ctx, req)
}

func (c *SimpleNotificationClient) BroadcastMessage(ctx context.Context, req *BroadcastRequest) (*NotificationResponse, error) {
	return c.service.BroadcastMessage(ctx, req)
}

func (c *SimpleNotificationClient) SubscribeNotifications(ctx context.Context, req *SubscriptionRequest) (NotificationService_SubscribeNotificationsClient, error) {
	return nil, fmt.Errorf("not implemented")
}

// ========== GRPC BUSINESS SERVICE (NO ACTUAL GRPC) ==========

type GRPCBusinessService struct {
	userClient         UserServiceClient
	paymentClient      PaymentServiceClient
	notificationClient NotificationServiceClient
}

func NewGRPCBusinessService() *GRPCBusinessService {
	return &GRPCBusinessService{
		userClient:         NewSimpleUserClient(),
		paymentClient:      NewSimplePaymentClient(),
		notificationClient: NewSimpleNotificationClient(),
	}
}

func (s *GRPCBusinessService) Close() {
	// Nothing to close in mock implementation
}

// Standard unary call workflow
func (s *GRPCBusinessService) OnboardUser(ctx context.Context, name, email string, amount float64) error {
	log.Printf("\nGRPC-BIZ: Starting user onboarding via gRPC")

	// Step 1: Create user
	user, err := s.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
		Name:       name,
		Email:      email,
	})
	if err != nil {
		return fmt.Errorf("user creation failed: %w", err)
	}

	log.Printf("GRPC-BIZ: User created with ID: %s", user.Id)

	// Step 2: Process payment
	payment, err := s.paymentClient.ProcessPayment(ctx, &PaymentRequest{
		UserId:   user.Id,
		Amount:   amount,
		Currency: "USD",
	})
	if err != nil {
		return fmt.Errorf("payment processing failed: %w", err)
	}

	log.Printf("GRPC-BIZ: Payment processed: %s", payment.TransactionId)

	// Step 3: Send notification
	_, err = s.notificationClient.SendNotification(ctx, &NotificationRequest{
		UserId:  user.Id,
		Message: "Welcome! Your account has been created.",
		Type:    NotificationType_EMAIL,
	})
	if err != nil {
		return fmt.Errorf("notification failed: %w", err)
	}

	log.Printf("GRPC-BIZ: Onboarding completed successfully")
	return nil
}

// Server streaming pattern
func (s *GRPCBusinessService) ListAllUsers(ctx context.Context) ([]*UserResponse, error) {
	log.Printf("\nGRPC-BIZ: Listing all users (server streaming)")

	stream, err := s.userClient.ListUsers(ctx, &ListUsersRequest{PageSize: 100})
	if err != nil {
		return nil, err
	}

	var users []*UserResponse
	for {
		user, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		users = append(users, user)
		log.Printf("GRPC-BIZ: Received user: %s", user.Name)
	}

	log.Printf("GRPC-BIZ: Total users received: %d", len(users))
	return users, nil
}

// Client streaming pattern
func (s *GRPCBusinessService) BatchProcessPayments(ctx context.Context, payments []*PaymentRequest) (*BatchPaymentResponse, error) {
	log.Printf("\nGRPC-BIZ: Batch processing %d payments (client streaming)", len(payments))

	stream, err := s.paymentClient.BatchProcessPayments(ctx)
	if err != nil {
		return nil, err
	}

	for _, payment := range payments {
		if err := stream.Send(payment); err != nil {
			return nil, err
		}
		log.Printf("GRPC-BIZ: Sent payment for user %s", payment.UserId)
	}

	result, err := stream.CloseAndRecv()
	if err != nil {
		return nil, err
	}

	log.Printf("GRPC-BIZ: Batch complete - Successful: %d, Failed: %d", result.Successful, result.Failed)
	return result, nil
}

// Bidirectional streaming pattern
func (s *GRPCBusinessService) StreamPaymentProcessing(ctx context.Context, payments []*PaymentRequest) error {
	log.Printf("\nGRPC-BIZ: Stream payment processing (bidirectional)")

	stream, err := s.paymentClient.StreamPayments(ctx)
	if err != nil {
		return err
	}

	waitc := make(chan struct{})

	// Receiving goroutine
	go func() {
		for {
			result, err := stream.Recv()
			if err == io.EOF {
				close(waitc)
				return
			}
			if err != nil {
				log.Printf("GRPC-BIZ: Error receiving: %v", err)
				close(waitc)
				return
			}
			log.Printf("GRPC-BIZ: Payment result received: %s - %s", result.TransactionId, result.Status)
		}
	}()

	// Sending
	for _, payment := range payments {
		if err := stream.Send(payment); err != nil {
			return err
		}
		time.Sleep(100 * time.Millisecond)
	}

	if err := stream.CloseSend(); err != nil {
		return err
	}

	<-waitc
	log.Printf("GRPC-BIZ: Stream processing completed")
	return nil
}

// Context with timeout
func (s *GRPCBusinessService) GetUserWithTimeout(userID string, timeout time.Duration) (*UserResponse, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	user, err := s.userClient.GetUser(ctx, &UserRequest{UserId: userID})
	if err != nil {
		return nil, fmt.Errorf("request timeout: %w", err)
	}

	return user, nil
}

// Error handling patterns
func (s *GRPCBusinessService) GetUserWithRetry(userID string, maxRetries int) (*UserResponse, error) {
	var lastErr error

	for i := 0; i < maxRetries; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		user, err := s.userClient.GetUser(ctx, &UserRequest{UserId: userID})
		cancel()

		if err == nil {
			return user, nil
		}

		lastErr = err
		log.Printf("GRPC-BIZ: Retry %d/%d failed: %v", i+1, maxRetries, err)
		time.Sleep(time.Duration(i+1) * 100 * time.Millisecond)
	}

	return nil, fmt.Errorf("all retries failed: %w", lastErr)
}

// Concurrent gRPC calls
func (s *GRPCBusinessService) GetUserProfile(ctx context.Context, userID string) (*UserResponse, *PaymentResponse, error) {
	log.Printf("\nGRPC-BIZ: Getting user profile concurrently")

	var user *UserResponse
	var payment *PaymentResponse
	var userErr, paymentErr error
	var wg sync.WaitGroup

	wg.Add(2)

	go func() {
		defer wg.Done()
		user, userErr = s.userClient.GetUser(ctx, &UserRequest{UserId: userID})
	}()

	go func() {
		defer wg.Done()
		payment, paymentErr = s.paymentClient.GetPaymentStatus(ctx, &PaymentStatusRequest{
			TransactionId: "txn-123",
		})
	}()

	wg.Wait()

	if userErr != nil {
		return nil, nil, userErr
	}
	if paymentErr != nil {
		return user, nil, paymentErr
	}

	log.Printf("GRPC-BIZ: Profile retrieved successfully")
	return user, payment, nil
}