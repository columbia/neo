package com.example.test;

// ========== MOCK GRPC BASE CLASSES (No imports needed) ==========

abstract class GrpcAbstractStub<T> {}
abstract class GrpcAbstractBlockingStub<T> extends GrpcAbstractStub<T> {}
abstract class GrpcAbstractAsyncStub<T> extends GrpcAbstractStub<T> {}

interface GrpcStreamObserver<T> {
    void onNext(T value);
    void onError(Throwable t);
    void onCompleted();
}

// ========== GRPC CLIENT STUBS & SERVER DEFINITIONS (The Contracts) ==========

// Contract for User Service
class GrpcUserService {
    // Client Stub
    public static class UserServiceBlockingStub extends GrpcAbstractBlockingStub<UserServiceBlockingStub> {
        public GrpcUser getUser(GrpcGetUserRequest r) { return new GrpcUser("grpc-user-123", "Mock User"); }
        public GrpcCreateUserResponse createUser(GrpcCreateUserRequest r) { return new GrpcCreateUserResponse("grpc-user-456"); }
    }
    // Server Base Class
    public static abstract class UserServiceImplBase {
        public void getUser(GrpcGetUserRequest r, GrpcStreamObserver<GrpcUser> o) {}
        public void createUser(GrpcCreateUserRequest r, GrpcStreamObserver<GrpcCreateUserResponse> o) {}
    }
}

// Contract for Payment Service
class GrpcPaymentService {
    // Client Stub
    public static class PaymentServiceBlockingStub extends GrpcAbstractBlockingStub<PaymentServiceBlockingStub> {
        public GrpcProcessPaymentResponse processPayment(GrpcProcessPaymentRequest r) { return new GrpcProcessPaymentResponse(true); }
    }
    // Server Base Class
    public static abstract class PaymentServiceImplBase {
        public void processPayment(GrpcProcessPaymentRequest r, GrpcStreamObserver<GrpcProcessPaymentResponse> o) {}
    }
}

// Contract for Order Service
class GrpcOrderService {
    // Client Stub
    public static class OrderServiceBlockingStub extends GrpcAbstractBlockingStub<OrderServiceBlockingStub> {
        public GrpcCreateOrderResponse createOrder(GrpcCreateOrderRequest r) { return new GrpcCreateOrderResponse("grpc-order-789"); }
    }
    // Server Base Class
    public static abstract class OrderServiceImplBase {
        public void createOrder(GrpcCreateOrderRequest r, GrpcStreamObserver<GrpcCreateOrderResponse> o) {}
    }
}

// ========== GRPC SERVICE IMPLEMENTATIONS (Inbound gRPC - The "Servers") ==========

class GrpcUserServiceImpl extends GrpcUserService.UserServiceImplBase {
    @Override
    public void getUser(GrpcGetUserRequest r, GrpcStreamObserver<GrpcUser> o) {
        System.out.println("GRPC-SERVER[User]: getUser called.");
        o.onNext(new GrpcUser("grpc-user-123", "John Doe"));
        o.onCompleted();
    }
}

class GrpcPaymentServiceImpl extends GrpcPaymentService.PaymentServiceImplBase {
    @Override
    public void processPayment(GrpcProcessPaymentRequest r, GrpcStreamObserver<GrpcProcessPaymentResponse> o) {
        System.out.println("GRPC-SERVER[Payment]: processPayment called.");
        o.onNext(new GrpcProcessPaymentResponse(true));
        o.onCompleted();
    }
}

class GrpcOrderServiceImpl extends GrpcOrderService.OrderServiceImplBase {
     @Override
    public void createOrder(GrpcCreateOrderRequest r, GrpcStreamObserver<GrpcCreateOrderResponse> o) {
        System.out.println("GRPC-SERVER[Order]: createOrder called.");
        o.onNext(new GrpcCreateOrderResponse("grpc-order-789"));
        o.onCompleted();
    }
}

// ========== BUSINESS SERVICE (The "Client" using the stubs) ==========

class GrpcBusinessService {
    private final GrpcUserService.UserServiceBlockingStub userStub;
    private final GrpcPaymentService.PaymentServiceBlockingStub paymentStub;
    private final GrpcOrderService.OrderServiceBlockingStub orderStub;

    GrpcBusinessService(GrpcUserService.UserServiceBlockingStub userStub,
                        GrpcPaymentService.PaymentServiceBlockingStub paymentStub,
                        GrpcOrderService.OrderServiceBlockingStub orderStub) {
        this.userStub = userStub;
        this.paymentStub = paymentStub;
        this.orderStub = orderStub;
    }

    void processComplexOrder(String userId, String productId, double amount) {
        System.out.println("\nGRPC-CLIENT: Starting complex order flow...");
        GrpcUser user = userStub.getUser(new GrpcGetUserRequest(userId));
        System.out.println("GRPC-CLIENT: Got user: " + user.getName());
        
        GrpcCreateOrderResponse orderResponse = orderStub.createOrder(new GrpcCreateOrderRequest(productId, amount));
        System.out.println("GRPC-CLIENT: Created order: " + orderResponse.getOrderId());

        GrpcProcessPaymentResponse paymentResponse = paymentStub.processPayment(new GrpcProcessPaymentRequest(amount));
        System.out.println("GRPC-CLIENT: Payment success: " + paymentResponse.isSuccess());
    }
}

// ========== GRPC DATA CLASSES (DTOs) ==========

class GrpcUser {
    private String id;
    private String name;
    public GrpcUser(String id, String name) { this.id = id; this.name = name; }
    public String getName() { return name; }
}
class GrpcGetUserRequest {
    public GrpcGetUserRequest(String userId) {}
}
class GrpcCreateUserRequest {
    public GrpcCreateUserRequest(String name) {}
}
class GrpcCreateUserResponse {
    private String userId;
    public GrpcCreateUserResponse(String id) { this.userId = id; }
}
class GrpcProcessPaymentRequest {
    public GrpcProcessPaymentRequest(double amount) {}
}
class GrpcProcessPaymentResponse {
    private boolean success;
    public GrpcProcessPaymentResponse(boolean s) { this.success = s; }
    public boolean isSuccess() { return success; }
}
class GrpcCreateOrderRequest {
    public GrpcCreateOrderRequest(String productId, double amount) {}
}
class GrpcCreateOrderResponse {
    private String orderId;
    public GrpcCreateOrderResponse(String id) { this.orderId = id; }
    public String getOrderId() { return orderId; }
}
