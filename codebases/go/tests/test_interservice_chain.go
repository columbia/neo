package tests

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/segmentio/kafka-go"
)

// ChainedServiceOrchestrator demonstrates complex multi-protocol communication chains
type ChainedServiceOrchestrator struct {
	httpBusiness *HTTPBusinessService
	grpcBusiness *GRPCBusinessService
	kafkaUser    *KafkaUserService
	kafkaBiz     *KafkaBusinessService
	rabbitmqUser *RabbitMQUserService
	rabbitmqBiz  *RabbitMQBusinessService
	redisUser    *RedisUserService
	redisBiz     *RedisBusinessService
}

// TEST 1: HTTP to gRPC to Kafka Chain - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) HTTPToGRPCToKafkaChain(ctx context.Context, name, email string, amount float64) error {
	log.Printf("\n=== CHAIN PATTERN 1: HTTP → gRPC → Kafka ===")

	httpUser, _, err := o.httpBusiness.OnboardUserWithResty(name, email, 50.0)
	if err != nil {
		return fmt.Errorf("HTTP step failed: %w", err)
	}

	grpcUser, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
		Name:       httpUser.Name,
		Email:      httpUser.Email,
	})
	if err != nil {
		return fmt.Errorf("gRPC step failed: %w", err)
	}

	kafkaUser, err := o.kafkaUser.CreateUser(ctx, grpcUser.Name, grpcUser.Email)
	if err != nil {
		return fmt.Errorf("Kafka step failed: %w", err)
	}

	log.Printf("Chain completed: HTTP(%s) → gRPC(%s) → Kafka(%s)",
		httpUser.ID, grpcUser.Id, kafkaUser.ID)

	return nil
}

// TEST 2: gRPC to Redis to RabbitMQ Chain - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) GRPCToRedisToRabbitMQChain(ctx context.Context, name, email string) error {
	log.Printf("\n=== CHAIN PATTERN 2: gRPC → Redis → RabbitMQ ===")

	grpcUser, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
		Name:  name,
		Email: email,
	})
	if err != nil {
		return fmt.Errorf("gRPC step failed: %w", err)
	}

	redisUser, err := o.redisUser.CreateUser(ctx, grpcUser.Name, grpcUser.Email)
	if err != nil {
		return fmt.Errorf("Redis step failed: %w", err)
	}

	rabbitmqUser, err := o.rabbitmqUser.CreateUser(redisUser.Name, redisUser.Email)
	if err != nil {
		return fmt.Errorf("RabbitMQ step failed: %w", err)
	}

	log.Printf("Chain completed: gRPC(%s) → Redis(%s) → RabbitMQ(%s)",
		grpcUser.Id, redisUser.ID, rabbitmqUser.ID)

	return nil
}

// TEST 3: Fan-Out to Multiple Services - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) FanOutPattern(ctx context.Context, name, email string) error {
	log.Printf("\n=== CHAIN PATTERN 3: Fan-Out to Multiple Services ===")

	var wg sync.WaitGroup
	errChan := make(chan error, 4)

	wg.Add(4)

	go func() {
		defer wg.Done()
		_, _, err := o.httpBusiness.OnboardUserWithResty(name, email, 100.0)
		if err != nil {
			errChan <- fmt.Errorf("HTTP fan-out error: %w", err)
		}
	}()

	go func() {
		defer wg.Done()
		_, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
			Name:  name,
			Email: email,
		})
		if err != nil {
			errChan <- fmt.Errorf("gRPC fan-out error: %w", err)
		}
	}()

	go func() {
		defer wg.Done()
		_, err := o.kafkaUser.CreateUser(ctx, name, email)
		if err != nil {
			errChan <- fmt.Errorf("Kafka fan-out error: %w", err)
		}
	}()

	go func() {
		defer wg.Done()
		_, err := o.redisUser.CreateUser(ctx, name, email)
		if err != nil {
			errChan <- fmt.Errorf("Redis fan-out error: %w", err)
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

// TEST 4: Conditional Protocol Routing - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) ConditionalRouting(ctx context.Context, userType string, name, email string) error {
	log.Printf("\n=== CHAIN PATTERN 4: Conditional Protocol Routing (%s) ===", userType)

	switch userType {
	case "premium":
		httpUser, _, err := o.httpBusiness.OnboardUserWithResty(name, email, 999.99)
		if err != nil {
			return err
		}

		grpcUser, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
			Name:  httpUser.Name,
			Email: httpUser.Email,
		})
		if err != nil {
			return err
		}

		_, err = o.redisUser.CreateUser(ctx, grpcUser.Name, grpcUser.Email)
		return err

	case "standard":
		_, err := o.kafkaUser.CreateUser(ctx, name, email)
		if err != nil {
			return err
		}

		_, err = o.rabbitmqUser.CreateUser(name, email)
		return err

	default:
		_, _, err := o.httpBusiness.OnboardUserWithResty(name, email, 99.99)
		return err
	}
}

// TEST 5: Batch Loop Processing - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) BatchProcessingLoop(ctx context.Context, users []struct{ Name, Email string }) error {
	log.Printf("\n=== CHAIN PATTERN 5: Batch Loop Processing (%d users) ===", len(users))

	for i, user := range users {
		log.Printf("Processing user %d/%d: %s", i+1, len(users), user.Name)

		_, _, err := o.httpBusiness.OnboardUserWithResty(user.Name, user.Email, 50.0)
		if err != nil {
			continue
		}

		_, err = o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
			Name:  user.Name,
			Email: user.Email,
		})
		if err != nil {
			continue
		}

		_, err = o.kafkaUser.CreateUser(ctx, user.Name, user.Email)
		if err != nil {
			continue
		}
	}

	return nil
}

// TEST 6: Error Propagation Chain - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) ErrorPropagationChain(ctx context.Context, name, email string) error {
	log.Printf("\n=== CHAIN PATTERN 6: Error Propagation ===")

	httpUser, _, err := o.httpBusiness.OnboardUserWithResty(name, email, 100.0)
	if err != nil {
		return fmt.Errorf("chain failed at HTTP step: %w", err)
	}

	timeoutCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	grpcUser, err := o.grpcBusiness.GetUserWithTimeout(httpUser.ID, 1*time.Second)
	if err != nil {
		redisUser, err := o.redisUser.CreateUser(timeoutCtx, name, email)
		if err != nil {
			return fmt.Errorf("chain failed at Redis fallback: %w", err)
		}

		log.Printf("Recovered using Redis fallback: %s", redisUser.ID)
		return nil
	}

	log.Printf("Chain completed successfully: %s", grpcUser.Id)
	return nil
}

// TEST 7: Context Propagation Chain - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) ContextPropagationChain(ctx context.Context, traceID, name, email string) error {
	log.Printf("\n=== CHAIN PATTERN 7: Context Propagation (TraceID: %s) ===", traceID)

	ctx = context.WithValue(ctx, "trace-id", traceID)
	ctx = context.WithValue(ctx, "user-agent", "test-orchestrator")

	ctxHTTP, cancelHTTP := context.WithTimeout(ctx, 5*time.Second)
	defer cancelHTTP()

	httpUser, err := o.httpBusiness.GetUserWithContext(ctxHTTP, "user-123")
	if err != nil {
		log.Printf("HTTP call failed (context may have expired): %v", err)
	} else {
		log.Printf("HTTP call completed with context: %s", httpUser.ID)
	}

	grpcUser, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
		Name:  name,
		Email: email,
	})
	if err != nil {
		return fmt.Errorf("gRPC with context failed: %w", err)
	}

	log.Printf("gRPC call completed with context: %s", grpcUser.Id)

	redisUser, err := o.redisUser.CreateUser(ctx, name, email)
	if err != nil {
		return fmt.Errorf("Redis with context failed: %w", err)
	}

	log.Printf("Redis call completed with context: %s", redisUser.ID)

	return nil
}

// TEST 8: Retry with Protocol Fallback - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) RetryWithProtocolFallback(ctx context.Context, name, email string, maxRetries int) error {
	log.Printf("\n=== CHAIN PATTERN 8: Retry with Protocol Fallback ===")

	protocols := []string{"HTTP", "gRPC", "Kafka", "Redis"}

	for i := 0; i < maxRetries; i++ {
		protocol := protocols[i%len(protocols)]

		var err error

		switch protocol {
		case "HTTP":
			_, _, err = o.httpBusiness.OnboardUserWithResty(name, email, 100.0)
		case "gRPC":
			_, err = o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
				Name:  name,
				Email: email,
			})
		case "Kafka":
			_, err = o.kafkaUser.CreateUser(ctx, name, email)
		case "Redis":
			_, err = o.redisUser.CreateUser(ctx, name, email)
		}

		if err == nil {
			log.Printf("Success using %s protocol", protocol)
			return nil
		}

		time.Sleep(time.Duration(i+1) * 100 * time.Millisecond)
	}

	return fmt.Errorf("all retry attempts failed")
}

// TEST 9: Aggregate from Multiple Sources - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) AggregateFromMultipleSources(ctx context.Context, userID string) (map[string]interface{}, error) {
	log.Printf("\n=== CHAIN PATTERN 9: Aggregate from Multiple Sources ===")

	result := make(map[string]interface{})
	var mu sync.Mutex
	var wg sync.WaitGroup

	wg.Add(4)

	go func() {
		defer wg.Done()
		user, _, err := o.httpBusiness.GetUserProfile(userID)
		if err == nil {
			mu.Lock()
			result["http_user"] = user
			mu.Unlock()
		}
	}()

	go func() {
		defer wg.Done()
		user, payment, err := o.grpcBusiness.GetUserProfile(ctx, userID)
		if err == nil {
			mu.Lock()
			result["grpc_user"] = user
			result["grpc_payment"] = payment
			mu.Unlock()
		}
	}()

	go func() {
		defer wg.Done()
		user, err := o.redisBiz.GetUserWithCache(ctx, userID)
		if err == nil {
			mu.Lock()
			result["redis_user"] = user
			mu.Unlock()
		}
	}()

	go func() {
		defer wg.Done()
		payment, exists := o.kafkaBiz.GetPaymentResult(userID)
		if exists {
			mu.Lock()
			result["kafka_payment"] = payment
			mu.Unlock()
		}
	}()

	wg.Wait()

	return result, nil
}

type SagaStep struct {
	Name     string
	Execute  func(context.Context) error
	Rollback func(context.Context) error
}

// TEST 10: Saga Pattern (Distributed Transaction) - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) SagaPattern(ctx context.Context, name, email string, amount float64) error {
	log.Printf("\n=== CHAIN PATTERN 10: Saga Pattern (Distributed Transaction) ===")

	var executedSteps []SagaStep

	steps := []SagaStep{
		{
			Name: "CreateHTTPUser",
			Execute: func(ctx context.Context) error {
				_, _, err := o.httpBusiness.OnboardUserWithResty(name, email, amount)
				return err
			},
			Rollback: func(ctx context.Context) error {
				log.Printf("  Rolling back HTTP user creation")
				return nil
			},
		},
		{
			Name: "CreateGRPCUser",
			Execute: func(ctx context.Context) error {
				_, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
					Name:  name,
					Email: email,
				})
				return err
			},
			Rollback: func(ctx context.Context) error {
				log.Printf("  Rolling back gRPC user creation")
				return nil
			},
		},
		{
			Name: "ProcessPayment",
			Execute: func(ctx context.Context) error {
				_, err := o.grpcBusiness.paymentClient.ProcessPayment(ctx, &PaymentRequest{
					UserId: "user-123",
					Amount: amount,
				})
				return err
			},
			Rollback: func(ctx context.Context) error {
				log.Printf("  Rolling back payment")
				return nil
			},
		},
		{
			Name: "PublishToKafka",
			Execute: func(ctx context.Context) error {
				_, err := o.kafkaUser.CreateUser(ctx, name, email)
				return err
			},
			Rollback: func(ctx context.Context) error {
				log.Printf("  Rolling back Kafka publish")
				return nil
			},
		},
	}

	for i, step := range steps {
		log.Printf("Executing step %d/%d: %s", i+1, len(steps), step.Name)

		if err := step.Execute(ctx); err != nil {
			log.Printf("Step %s failed: %v", step.Name, err)

			for j := len(executedSteps) - 1; j >= 0; j-- {
				if err := executedSteps[j].Rollback(ctx); err != nil {
					log.Printf("  Rollback failed for %s: %v", executedSteps[j].Name, err)
				}
			}

			return fmt.Errorf("saga failed at step %s: %w", step.Name, err)
		}

		executedSteps = append(executedSteps, step)
	}

	return nil
}

// TEST 11: Stream Processing Chain - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) StreamProcessingChain(ctx context.Context) error {
	log.Printf("\n=== CHAIN PATTERN 11: Stream Processing ===")

	stream, err := o.grpcBusiness.userClient.ListUsers(ctx, &ListUsersRequest{PageSize: 10})
	if err != nil {
		return err
	}

	var processedCount int

	for {
		user, err := stream.Recv()
		if err != nil {
			break
		}

		kafkaUser, err := o.kafkaUser.CreateUser(ctx, user.Name, user.Email)
		if err != nil {
			continue
		}

		_, err = o.redisUser.CreateUser(ctx, kafkaUser.Name, kafkaUser.Email)
		if err != nil {
			continue
		}

		processedCount++
	}

	log.Printf("Stream processing completed: %d users", processedCount)
	return nil
}

// TEST 12: User Input to Privileged Operation - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) TaintFlowUserInputToPrivilegedOperation(ctx context.Context, userInput string) error {
	log.Printf("\n=== TAINT FLOW TEST: User Input → Services → Privileged Op ===")

	httpUser, _, err := o.httpBusiness.OnboardUserWithResty(userInput, userInput+"@test.com", 100.0)
	if err != nil {
		return err
	}

	grpcUser, err := o.grpcBusiness.userClient.CreateUser(ctx, &GRPCCreateUserRequest{
		Name:  httpUser.Name,
		Email: httpUser.Email,
	})
	if err != nil {
		return err
	}

	_, err = o.kafkaUser.CreateUser(ctx, grpcUser.Name, grpcUser.Email)
	if err != nil {
		return err
	}

	return executePrivilegedOperation(grpcUser.Name)
}

func executePrivilegedOperation(data string) error {
	log.Printf("PRIVILEGED OPERATION: Processing data: %s", data)
	return nil
}

// TEST 13: Serialize and Transmit to Multiple Services - SHOULD BE DETECTED
func (o *ChainedServiceOrchestrator) SerializeAndTransmit(ctx context.Context, data interface{}) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	_, err = o.httpBusiness.RawHTTPCall("POST", "http://localhost:8001/data", jsonData)
	if err != nil {
		log.Printf("HTTP transmission failed: %v", err)
	}

	event := KafkaEvent{
		EventType: "DATA_TRANSMITTED",
		Timestamp: time.Now(),
		Data:      jsonData,
	}

	eventJSON, _ := json.Marshal(event)
	o.kafkaUser.writer.WriteMessages(ctx, kafka.Message{Value: eventJSON})

	o.redisUser.client.Set(ctx, "transmitted:data", jsonData, 5*time.Minute)

	return nil
}

// TEST 14: Internal Data Only - SHOULD NOT BE DETECTED
func (o *ChainedServiceOrchestrator) InternalDataFlow(ctx context.Context) error {
	log.Printf("\n=== TEST 14: Internal Data Only ===")

	// Only using hardcoded/internal data
	internalConfig := "internal-system-config"
	systemRole := "admin"
	staticData := map[string]string{
		"config": internalConfig,
		"role":   systemRole,
	}

	// Process internal data without any external service calls
	return processInternalData(staticData)
}

// TEST 15: Hardcoded Values Only - SHOULD NOT BE DETECTED
func (o *ChainedServiceOrchestrator) HardcodedValuesFlow(ctx context.Context) error {
	log.Printf("\n=== TEST 15: Hardcoded Values Only ===")

	// Using only hardcoded values
	hardcodedName := "system-user"
	hardcodedEmail := "system@internal.local"
	hardcodedAmount := 0.0

	// No external service calls, just internal processing
	result := fmt.Sprintf("Processing internal user: %s <%s> with amount: %.2f",
		hardcodedName, hardcodedEmail, hardcodedAmount)

	log.Printf("Internal result: %s", result)
	return nil
}

// TEST 16: Local Computation Only - SHOULD NOT BE DETECTED
func (o *ChainedServiceOrchestrator) LocalComputationOnly(ctx context.Context, input int) (int, error) {
	log.Printf("\n=== TEST 16: Local Computation Only ===")

	// Pure computation without any service calls
	result := input * 2
	for i := 0; i < 5; i++ {
		result = result + i*i
	}

	// Local data transformation
	data := map[string]int{
		"original": input,
		"computed": result,
	}

	log.Printf("Computation result: %v", data)
	return result, nil
}

// TEST 17: Internal Helper Call Only - SHOULD NOT BE DETECTED
func (o *ChainedServiceOrchestrator) InternalHelperOnly(ctx context.Context) error {
	log.Printf("\n=== TEST 17: Internal Helper Call Only ===")

	// Only calling internal helper functions
	config := getInternalConfig()
	validated := validateInternalData(config)

	return processInternalData(validated)
}

// Helper functions for negative test cases
func getInternalConfig() map[string]string {
	return map[string]string{
		"env":     "production",
		"version": "1.0.0",
	}
}

func validateInternalData(data map[string]string) map[string]string {
	// Just return the data as-is for this test
	return data
}

func processInternalData(data map[string]string) error {
	log.Printf("Processing internal data: %v", data)
	return nil
}

/*
Expected Results:
✅ 13 flows should be detected (tests 1-13)
❌ 4 flows should NOT be detected (tests 14-17)
*/