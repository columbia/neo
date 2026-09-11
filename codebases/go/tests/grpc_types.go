package tests

// ========== MANUAL GRPC TYPE DEFINITIONS (NO PROTOC NEEDED) ==========
// This file replaces the need for .proto files and protoc compilation

import (
	"context"
	"io"
)

// ========== USER SERVICE TYPES ==========

type UserRequest struct {
	UserId string
}

type GRPCCreateUserRequest struct {
	Name       string
	Email      string
}

type UpdateUserRequest struct {
	UserId string
	Name   string
	Email  string
}

type UserResponse struct {
	Id         string
	Name       string
	Email      string
	Department string
}

type ListUsersRequest struct {
	PageSize  int32
	PageToken string
}

type DeleteResponse struct {
	Success bool
	Message string
}

// ========== PAYMENT SERVICE TYPES ==========

type PaymentRequest struct {
	UserId      string
	Amount      float64
	Currency    string
	Description string
}

type PaymentResponse struct {
	Success       bool
	TransactionId string
	UserId        string
	Amount        float64
	Status        string
	Message       string
}

type PaymentStatusRequest struct {
	TransactionId string
}

type BatchPaymentResponse struct {
	TotalProcessed int32
	Successful     int32
	Failed         int32
	Results        []*PaymentResponse
}

// ========== NOTIFICATION SERVICE TYPES ==========

type NotificationType int32

const (
	NotificationType_EMAIL  NotificationType = 0
	NotificationType_SMS    NotificationType = 1
	NotificationType_PUSH   NotificationType = 2
	NotificationType_IN_APP NotificationType = 3
)

type NotificationRequest struct {
	UserId  string
	Message string
	Type    NotificationType
}

type BroadcastRequest struct {
	Message string
	UserIds []string
	Type    NotificationType
}

type NotificationResponse struct {
	Success         bool
	Message         string
	RecipientsCount int32
}

type SubscriptionRequest struct {
	UserId string
	Types  []NotificationType
}

type NotificationMessage struct {
	Id        string
	UserId    string
	Message   string
	Type      NotificationType
	Timestamp int64
}

// ========== DATA STREAM SERVICE TYPES ==========

type StreamRequest struct {
	BatchSize int32
	Filter    string
}

type DataChunk struct {
	Id       string
	Data     []byte
	Sequence int32
	IsLast   bool
}

type UploadResponse struct {
	Success        bool
	ChunksReceived int32
	TotalBytes     int64
}

// ========== SERVICE INTERFACES (CLIENT SIDE) ==========

// UserServiceClient defines the client interface for user operations
type UserServiceClient interface {
	GetUser(ctx context.Context, req *UserRequest) (*UserResponse, error)
	CreateUser(ctx context.Context, req *GRPCCreateUserRequest) (*UserResponse, error)
	UpdateUser(ctx context.Context, req *UpdateUserRequest) (*UserResponse, error)
	DeleteUser(ctx context.Context, req *UserRequest) (*DeleteResponse, error)
	ListUsers(ctx context.Context, req *ListUsersRequest) (UserService_ListUsersClient, error)
	StreamUserUpdates(ctx context.Context, req *UserRequest) (UserService_StreamUserUpdatesClient, error)
}

// UserService_ListUsersClient is the streaming client for ListUsers
type UserService_ListUsersClient interface {
	Recv() (*UserResponse, error)
}

// UserService_StreamUserUpdatesClient is the streaming client for StreamUserUpdates
type UserService_StreamUserUpdatesClient interface {
	Recv() (*UserResponse, error)
}

// PaymentServiceClient defines the client interface for payment operations
type PaymentServiceClient interface {
	ProcessPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error)
	RefundPayment(ctx context.Context, req *PaymentRequest) (*PaymentResponse, error)
	GetPaymentStatus(ctx context.Context, req *PaymentStatusRequest) (*PaymentResponse, error)
	BatchProcessPayments(ctx context.Context) (PaymentService_BatchProcessPaymentsClient, error)
	StreamPayments(ctx context.Context) (PaymentService_StreamPaymentsClient, error)
}

// PaymentService_BatchProcessPaymentsClient is the client streaming interface
type PaymentService_BatchProcessPaymentsClient interface {
	Send(*PaymentRequest) error
	CloseAndRecv() (*BatchPaymentResponse, error)
}

// PaymentService_StreamPaymentsClient is the bidirectional streaming interface
type PaymentService_StreamPaymentsClient interface {
	Send(*PaymentRequest) error
	Recv() (*PaymentResponse, error)
	CloseSend() error
}

// NotificationServiceClient defines the client interface for notifications
type NotificationServiceClient interface {
	SendNotification(ctx context.Context, req *NotificationRequest) (*NotificationResponse, error)
	BroadcastMessage(ctx context.Context, req *BroadcastRequest) (*NotificationResponse, error)
	SubscribeNotifications(ctx context.Context, req *SubscriptionRequest) (NotificationService_SubscribeNotificationsClient, error)
}

// NotificationService_SubscribeNotificationsClient is the streaming client
type NotificationService_SubscribeNotificationsClient interface {
	Recv() (*NotificationMessage, error)
}

// ========== SERVICE INTERFACES (SERVER SIDE) ==========

// UserServiceServer defines the server interface
type UserServiceServer interface {
	GetUser(context.Context, *UserRequest) (*UserResponse, error)
	CreateUser(context.Context, *GRPCCreateUserRequest) (*UserResponse, error)
	UpdateUser(context.Context, *UpdateUserRequest) (*UserResponse, error)
	DeleteUser(context.Context, *UserRequest) (*DeleteResponse, error)
	ListUsers(*ListUsersRequest, UserService_ListUsersServer) error
	StreamUserUpdates(*UserRequest, UserService_StreamUserUpdatesServer) error
}

// UserService_ListUsersServer is the server streaming interface
type UserService_ListUsersServer interface {
	Send(*UserResponse) error
}

// UserService_StreamUserUpdatesServer is the server streaming interface
type UserService_StreamUserUpdatesServer interface {
	Send(*UserResponse) error
}

// PaymentServiceServer defines the server interface
type PaymentServiceServer interface {
	ProcessPayment(context.Context, *PaymentRequest) (*PaymentResponse, error)
	RefundPayment(context.Context, *PaymentRequest) (*PaymentResponse, error)
	GetPaymentStatus(context.Context, *PaymentStatusRequest) (*PaymentResponse, error)
	BatchProcessPayments(PaymentService_BatchProcessPaymentsServer) error
	StreamPayments(PaymentService_StreamPaymentsServer) error
}

// PaymentService_BatchProcessPaymentsServer is the server streaming interface
type PaymentService_BatchProcessPaymentsServer interface {
	Recv() (*PaymentRequest, error)
	SendAndClose(*BatchPaymentResponse) error
}

// PaymentService_StreamPaymentsServer is the bidirectional server interface
type PaymentService_StreamPaymentsServer interface {
	Send(*PaymentResponse) error
	Recv() (*PaymentRequest, error)
}

// NotificationServiceServer defines the server interface
type NotificationServiceServer interface {
	SendNotification(context.Context, *NotificationRequest) (*NotificationResponse, error)
	BroadcastMessage(context.Context, *BroadcastRequest) (*NotificationResponse, error)
	SubscribeNotifications(*SubscriptionRequest, NotificationService_SubscribeNotificationsServer) error
}

// NotificationService_SubscribeNotificationsServer is the server streaming interface
type NotificationService_SubscribeNotificationsServer interface {
	Send(*NotificationMessage) error
}

// UnimplementedUserServiceServer provides default implementations
type UnimplementedUserServiceServer struct{}

func (*UnimplementedUserServiceServer) GetUser(context.Context, *UserRequest) (*UserResponse, error) {
	return nil, nil
}
func (*UnimplementedUserServiceServer) CreateUser(context.Context, *GRPCCreateUserRequest) (*UserResponse, error) {
	return nil, nil
}
func (*UnimplementedUserServiceServer) UpdateUser(context.Context, *UpdateUserRequest) (*UserResponse, error) {
	return nil, nil
}
func (*UnimplementedUserServiceServer) DeleteUser(context.Context, *UserRequest) (*DeleteResponse, error) {
	return nil, nil
}
func (*UnimplementedUserServiceServer) ListUsers(*ListUsersRequest, UserService_ListUsersServer) error {
	return nil
}
func (*UnimplementedUserServiceServer) StreamUserUpdates(*UserRequest, UserService_StreamUserUpdatesServer) error {
	return nil
}

// UnimplementedPaymentServiceServer provides default implementations
type UnimplementedPaymentServiceServer struct{}

func (*UnimplementedPaymentServiceServer) ProcessPayment(context.Context, *PaymentRequest) (*PaymentResponse, error) {
	return nil, nil
}
func (*UnimplementedPaymentServiceServer) RefundPayment(context.Context, *PaymentRequest) (*PaymentResponse, error) {
	return nil, nil
}
func (*UnimplementedPaymentServiceServer) GetPaymentStatus(context.Context, *PaymentStatusRequest) (*PaymentResponse, error) {
	return nil, nil
}
func (*UnimplementedPaymentServiceServer) BatchProcessPayments(PaymentService_BatchProcessPaymentsServer) error {
	return nil
}
func (*UnimplementedPaymentServiceServer) StreamPayments(PaymentService_StreamPaymentsServer) error {
	return nil
}

// UnimplementedNotificationServiceServer provides default implementations
type UnimplementedNotificationServiceServer struct{}

func (*UnimplementedNotificationServiceServer) SendNotification(context.Context, *NotificationRequest) (*NotificationResponse, error) {
	return nil, nil
}
func (*UnimplementedNotificationServiceServer) BroadcastMessage(context.Context, *BroadcastRequest) (*NotificationResponse, error) {
	return nil, nil
}
func (*UnimplementedNotificationServiceServer) SubscribeNotifications(*SubscriptionRequest, NotificationService_SubscribeNotificationsServer) error {
	return nil
}

// ========== MOCK IMPLEMENTATIONS FOR TESTING ==========

// mockListUsersClient implements UserService_ListUsersClient
type mockListUsersClient struct {
	users []*UserResponse
	index int
}

func (m *mockListUsersClient) Recv() (*UserResponse, error) {
	if m.index >= len(m.users) {
		return nil, io.EOF
	}
	user := m.users[m.index]
	m.index++
	return user, nil
}

// mockBatchPaymentsClient implements PaymentService_BatchProcessPaymentsClient
type mockBatchPaymentsClient struct {
	requests []*PaymentRequest
}

func (m *mockBatchPaymentsClient) Send(req *PaymentRequest) error {
	m.requests = append(m.requests, req)
	return nil
}

func (m *mockBatchPaymentsClient) CloseAndRecv() (*BatchPaymentResponse, error) {
	return &BatchPaymentResponse{
		TotalProcessed: int32(len(m.requests)),
		Successful:     int32(len(m.requests)),
		Failed:         0,
	}, nil
}

// mockStreamPaymentsClient implements PaymentService_StreamPaymentsClient
type mockStreamPaymentsClient struct {
	sendChan chan *PaymentRequest
	recvChan chan *PaymentResponse
}

func (m *mockStreamPaymentsClient) Send(req *PaymentRequest) error {
	m.sendChan <- req
	return nil
}

func (m *mockStreamPaymentsClient) Recv() (*PaymentResponse, error) {
	resp, ok := <-m.recvChan
	if !ok {
		return nil, io.EOF
	}
	return resp, nil
}

func (m *mockStreamPaymentsClient) CloseSend() error {
	close(m.sendChan)
	return nil
}