package main

import (
	"context"
	"fmt"
	"log"
	"microservices-test-go/tests"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	log.SetFlags(0)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		cancel()
	}()

	if err := runAllTests(ctx); err != nil {
		log.Fatalf("Test suite failed: %v", err)
	}
}

func runAllTests(ctx context.Context) error {
	if err := testHTTPCommunication(ctx); err != nil {
		return fmt.Errorf("HTTP test failed: %w", err)
	}

	if err := testGRPCCommunication(ctx); err != nil {
		return fmt.Errorf("gRPC test failed: %w", err)
	}

	if err := testKafkaCommunication(ctx); err != nil {
		return fmt.Errorf("Kafka test failed: %w", err)
	}

	if err := testRabbitMQCommunication(ctx); err != nil {
		return fmt.Errorf("RabbitMQ test failed: %w", err)
	}

	if err := testRedisCommunication(ctx); err != nil {
		return fmt.Errorf("Redis test failed: %w", err)
	}

	return nil
}

func testHTTPCommunication(ctx context.Context) error {
	userService := tests.NewHTTPUserService()
	if err := userService.Start(8001); err != nil {
		return err
	}
	defer userService.Shutdown(ctx)

	paymentService := tests.NewHTTPPaymentService()
	if err := paymentService.Start(8002); err != nil {
		return err
	}
	defer paymentService.Shutdown(ctx)

	businessService := tests.NewHTTPBusinessService(
		"http://localhost:8001",
		"http://localhost:8002",
	)

	user, payment, err := businessService.OnboardUserWithResty("Alice", "alice@test.com", 99.99)
	if err != nil {
		return err
	}
	_ = user
	_ = payment

	user2, payment2, err := businessService.OnboardUserWithNetHTTP("Bob", "bob@test.com", 149.99)
	if err != nil {
		return err
	}
	_ = user2
	_ = payment2

	_, payments, err := businessService.GetUserProfile(user.ID)
	if err != nil {
		return err
	}
	_ = payments

	timeoutCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	contextUser, err := businessService.GetUserWithContext(timeoutCtx, user.ID)
	if err != nil {
		return err
	}
	_ = contextUser

	_, _, _ = businessService.OnboardWithRetry("Charlie", "charlie@test.com", 199.99, 3)

	if err := businessService.ChainedOperations("David", "david@test.com"); err != nil {
		return err
	}

	if err := businessService.BroadcastToMultipleServices(user.ID); err != nil {
		return err
	}

	return nil
}

func testGRPCCommunication(ctx context.Context) error {
	businessService := tests.NewGRPCBusinessService()
	defer businessService.Close()

	if err := businessService.OnboardUser(ctx, "Eve", "eve@test.com", 299.99); err != nil {
		return err
	}

	users, err := businessService.ListAllUsers(ctx)
	if err != nil {
		return err
	}
	_ = users

	payments := []*tests.PaymentRequest{
		{UserId: "user-1", Amount: 100.0},
		{UserId: "user-2", Amount: 200.0},
		{UserId: "user-3", Amount: 300.0},
	}
	result, err := businessService.BatchProcessPayments(ctx, payments)
	if err != nil {
		return err
	}
	_ = result

	if err := businessService.StreamPaymentProcessing(ctx, payments); err != nil {
		return err
	}

	_, _ = businessService.GetUserWithTimeout("user-123", 2*time.Second)
	_, _ = businessService.GetUserWithRetry("user-456", 3)
	_, _, _ = businessService.GetUserProfile(ctx, "user-789")

	return nil
}

func testKafkaCommunication(ctx context.Context) error {
	brokers := []string{"localhost:9092"}

	if err := tests.CheckKafkaHealth(brokers); err != nil {
		return nil
	}

	topics := []string{tests.TopicUserEvents, tests.TopicPaymentEvents}
	_ = tests.CreateKafkaTopics(brokers, topics)

	userService := tests.NewKafkaUserService(brokers)
	defer userService.Close()

	paymentService := tests.NewKafkaPaymentService(brokers, "payment-service-group")
	defer paymentService.Close()

	businessService := tests.NewKafkaBusinessService(brokers, userService)
	defer businessService.Close()

	paymentCtx, paymentCancel := context.WithCancel(ctx)
	defer paymentCancel()
	go paymentService.StartListening(paymentCtx)

	businessCtx, businessCancel := context.WithCancel(ctx)
	defer businessCancel()
	go businessService.StartListening(businessCtx)

	time.Sleep(2 * time.Second)

	user, err := businessService.OnboardUserAndMakePayment(ctx, "Frank", "frank@kafka.com")
	if err != nil {
		return err
	}
	_ = user

	time.Sleep(3 * time.Second)

	payment, exists := businessService.GetPaymentResult(user.ID)
	_ = payment
	_ = exists

	return nil
}

func testRabbitMQCommunication(ctx context.Context) error {
	url := "amqp://guest:guest@localhost:5672/"

	userService, err := tests.NewRabbitMQUserService(url)
	if err != nil {
		return nil
	}
	defer userService.Close()

	paymentService, err := tests.NewRabbitMQPaymentService(url)
	if err != nil {
		return err
	}
	defer paymentService.Close()

	businessService, err := tests.NewRabbitMQBusinessService(url, userService)
	if err != nil {
		return err
	}
	defer businessService.Close()

	if err := paymentService.StartListening(); err != nil {
		return err
	}

	if err := businessService.StartListening(); err != nil {
		return err
	}

	time.Sleep(2 * time.Second)

	user, err := businessService.OnboardUserAndMakePayment("Grace", "grace@rabbitmq.com")
	if err != nil {
		return err
	}
	_ = user

	time.Sleep(3 * time.Second)

	payment, exists := businessService.GetPaymentResult(user.ID)
	_ = payment
	_ = exists

	rpcClient, err := tests.NewRabbitMQRPCClient(url)
	if err == nil {
		defer rpcClient.Close()
	}

	return nil
}

func testRedisCommunication(ctx context.Context) error {
	addr := "localhost:6379"

	userService := tests.NewRedisUserService(addr)
	defer userService.Close()

	if err := userService.Ping(ctx); err != nil {
		return nil
	}

	paymentService := tests.NewRedisPaymentService(addr)
	defer paymentService.Close()

	cacheService := tests.NewRedisCacheService(addr)
	defer cacheService.Close()

	businessService := tests.NewRedisBusinessService(addr, userService, cacheService)
	defer businessService.Close()

	paymentCtx, paymentCancel := context.WithCancel(ctx)
	defer paymentCancel()
	go paymentService.StartListening(paymentCtx)

	businessCtx, businessCancel := context.WithCancel(ctx)
	defer businessCancel()
	go businessService.StartListening(businessCtx)

	time.Sleep(1 * time.Second)

	user, err := businessService.CreateUserWithCache(ctx, "Hannah", "hannah@redis.com")
	if err != nil {
		return err
	}

	cachedUser, err := businessService.GetUserWithCache(ctx, user.ID)
	if err != nil {
		return err
	}
	_ = cachedUser

	if err := businessService.UpdateUserAndInvalidateCache(ctx, user.ID, "Hannah Updated", "hannah.updated@redis.com"); err != nil {
		return err
	}

	time.Sleep(2 * time.Second)

	payment, exists := businessService.GetPaymentResult(user.ID)
	_ = payment
	_ = exists

	lock := tests.NewRedisDistributedLock(userService.GetClient(), "test-resource", 5*time.Second)
	acquired, err := lock.Acquire(ctx)
	if err != nil {
		return err
	}
	if acquired {
		defer lock.Release(ctx)
	}

	deleted, err := cacheService.InvalidatePattern(ctx, "user:*")
	if err != nil {
		return err
	}
	_ = deleted

	return nil
}