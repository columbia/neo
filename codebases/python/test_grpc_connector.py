# comprehensive_concise_grpc_test.py
"""
Comprehensive yet concise gRPC test code for CodeQL testing.
Covers all major gRPC patterns in minimal code.
"""

import asyncio
import grpc
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncIterator

logger = logging.getLogger(__name__)

# ========== MESSAGE CLASSES ==========

@dataclass
class UserRequest:
    user_id: str

@dataclass
class CreateUserRequest:
    name: str
    email: str
    department: str = "Engineering"

@dataclass
class UserResponse:
    id: str
    name: str
    email: str

@dataclass
class PaymentRequest:
    user_id: str
    amount: float

@dataclass
class PaymentResponse:
    success: bool
    transaction_id: str

@dataclass
class NotificationRequest:
    user_id: str
    message: str

@dataclass
class StreamRequest:
    batch_size: int

# ========== GRPC SERVICER INTERFACES ==========

class UserServiceServicer(ABC):
    @abstractmethod
    def GetUser(self, request: UserRequest, context) -> UserResponse:
        pass
    
    @abstractmethod
    def CreateUser(self, request: CreateUserRequest, context) -> UserResponse:
        pass

class PaymentServiceServicer(ABC):
    @abstractmethod
    def ProcessPayment(self, request: PaymentRequest, context) -> PaymentResponse:
        pass

# ========== GRPC STUBS (Various Naming Patterns) ==========

class UserServiceStub:
    def __init__(self, channel):
        self.channel = channel
    
    def GetUser(self, request: UserRequest) -> UserResponse:
        """Standard gRPC call"""
        pass
    
    def CreateUser(self, request: CreateUserRequest) -> UserResponse:
        """Another standard call"""
        pass
    
    def UpdateUserProfile(self, request: CreateUserRequest) -> UserResponse:
        """PascalCase method"""
        pass
    
    def deleteUser(self, request: UserRequest) -> UserResponse:
        """camelCase method"""
        pass

class PaymentServiceStub:
    def __init__(self, channel):
        self.channel = channel
    
    def ProcessPayment(self, request: PaymentRequest) -> PaymentResponse:
        pass
    
    def RefundPayment(self, request: PaymentRequest) -> PaymentResponse:
        pass

class NotificationServiceStub:
    def __init__(self, channel):
        self.channel = channel
    
    def SendNotification(self, request: NotificationRequest):
        pass
    
    def BroadcastMessage(self, request: NotificationRequest):
        pass

class DataStreamStub:
    def __init__(self, channel):
        self.channel = channel
    
    def StreamData(self, request: StreamRequest) -> AsyncIterator:
        """Streaming gRPC call"""
        pass
    
    def UploadStream(self, request_iterator) -> UserResponse:
        """Client streaming"""
        pass

# ========== EXTENDED STUB PATTERNS ==========

class AdvancedUserStub(UserServiceStub):
    """Inheritance pattern"""
    
    def GetUserAdvanced(self, request: UserRequest) -> UserResponse:
        pass

class CustomServiceClient:
    """Non-standard naming but still gRPC"""
    
    def __init__(self, channel):
        self.channel = channel
    
    def CallCustomMethod(self, request):
        pass

# ========== SERVICE IMPLEMENTATIONS ==========

class UserServiceImpl(UserServiceServicer):
    def GetUser(self, request: UserRequest, context) -> UserResponse:
        logger.info(f"GetUser called for {request.user_id}")
        return UserResponse("1", "Test User", "test@example.com")
    
    def CreateUser(self, request: CreateUserRequest, context) -> UserResponse:
        logger.info(f"CreateUser called for {request.name}")
        return UserResponse("1", request.name, request.email)

# ========== BUSINESS SERVICES ==========

class OrderProcessingService:
    """Main business service with various gRPC patterns"""
    
    def __init__(self):
        # Multiple stub types
        self.user_stub: Optional[UserServiceStub] = None
        self.payment_stub: Optional[PaymentServiceStub] = None
        self.notification_stub: Optional[NotificationServiceStub] = None
        self.stream_stub: Optional[DataStreamStub] = None
        self.advanced_stub: Optional[AdvancedUserStub] = None
        self.custom_client: Optional[CustomServiceClient] = None
    
    async def initialize_connections(self):
        """Initialize various gRPC connections"""
        # Standard channel creation
        user_channel = grpc.aio.insecure_channel('localhost:50051')
        payment_channel = grpc.aio.insecure_channel('localhost:50052')
        notification_channel = grpc.aio.insecure_channel('localhost:50053')
        
        # Secure channel
        stream_channel = grpc.aio.secure_channel('localhost:50054', grpc.ssl_channel_credentials())
        
        # Custom address patterns
        advanced_channel = grpc.aio.insecure_channel('user-service:8080')
        custom_channel = grpc.aio.insecure_channel('custom.example.com:9090')
        
        # Create stubs
        self.user_stub = UserServiceStub(user_channel)
        self.payment_stub = PaymentServiceStub(payment_channel)
        self.notification_stub = NotificationServiceStub(notification_channel)
        self.stream_stub = DataStreamStub(stream_channel)
        self.advanced_stub = AdvancedUserStub(advanced_channel)
        self.custom_client = CustomServiceClient(custom_channel)
    
    async def standard_grpc_workflow(self, name: str, email: str, amount: float):
        """Standard gRPC calls"""
        
        # Basic stub calls
        create_req = CreateUserRequest(name, email)
        user = self.user_stub.CreateUser(create_req)
        
        # Payment processing
        pay_req = PaymentRequest(user.id, amount)
        payment = self.payment_stub.ProcessPayment(pay_req)
        
        # Notification
        notif_req = NotificationRequest(user.id, "Order processed")
        self.notification_stub.SendNotification(notif_req)
        
        return user, payment
    
    async def advanced_grpc_patterns(self, user_id: str):
        """Advanced gRPC call patterns"""
        
        # Different method naming styles
        req = UserRequest(user_id)
        user1 = self.user_stub.GetUser(req)  # PascalCase
        user2 = self.user_stub.deleteUser(req)  # camelCase
        user3 = self.advanced_stub.GetUserAdvanced(req)  # Inherited method
        
        # Custom client calls
        custom_result = self.custom_client.CallCustomMethod(req)
        
        # Broadcast pattern
        notif_req = NotificationRequest(user_id, "Broadcast message")
        self.notification_stub.BroadcastMessage(notif_req)
        
        return user1, user2, user3
    
    async def streaming_grpc_calls(self):
        """Streaming gRPC patterns"""
        
        # Server streaming
        stream_req = StreamRequest(100)
        async for data in self.stream_stub.StreamData(stream_req):
            logger.info(f"Received stream data: {data}")
        
        # Client streaming simulation
        async def request_generator():
            for i in range(5):
                yield CreateUserRequest(f"User{i}", f"user{i}@test.com")
        
        result = self.stream_stub.UploadStream(request_generator())
        return result
    
    def sync_grpc_calls(self, user_id: str):
        """Synchronous gRPC calls (non-async)"""
        
        req = UserRequest(user_id)
        
        # Sync calls to different services
        user = self.user_stub.GetUser(req)
        updated = self.user_stub.UpdateUserProfile(CreateUserRequest("Updated", "new@test.com"))
        
        # Refund call
        refund_req = PaymentRequest(user_id, 50.0)
        refund = self.payment_stub.RefundPayment(refund_req)
        
        return user, updated, refund

class UserManagementService:
    """Another service with different patterns"""
    
    def __init__(self):
        self.user_stub: Optional[UserServiceStub] = None
    
    async def setup(self):
        """Different initialization pattern"""
        channel = grpc.aio.insecure_channel('user-management:8081')
        self.user_stub = UserServiceStub(channel)
    
    def manage_user(self, user_id: str, operation: str):
        """Conditional gRPC calls"""
        
        req = UserRequest(user_id)
        
        if operation == "get":
            return self.user_stub.GetUser(req)
        elif operation == "delete":
            return self.user_stub.deleteUser(req)
        else:
            # Default operation
            profile_req = CreateUserRequest("Default", "default@test.com")
            return self.user_stub.UpdateUserProfile(profile_req)
    
    def batch_operations(self, user_ids: list):
        """Multiple calls in loop"""
        
        results = []
        for user_id in user_ids:
            req = UserRequest(user_id)
            user = self.user_stub.GetUser(req)
            results.append(user)
        
        return results

# ========== ERROR HANDLING PATTERNS ==========

class RobustGrpcService:
    """Service with error handling"""
    
    def __init__(self):
        self.payment_stub: Optional[PaymentServiceStub] = None
    
    async def init(self):
        channel = grpc.aio.insecure_channel('payment:8082')
        self.payment_stub = PaymentServiceStub(channel)
    
    async def safe_payment(self, user_id: str, amount: float):
        """gRPC call with error handling"""
        
        try:
            req = PaymentRequest(user_id, amount)
            result = self.payment_stub.ProcessPayment(req)
            return result
        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e}")
            # Retry with different call
            retry_req = PaymentRequest(user_id, amount * 0.5)
            return self.payment_stub.ProcessPayment(retry_req)

# ========== TEST RUNNER ==========

async def run_comprehensive_test():
    """Test all gRPC patterns"""
    
    # Initialize services
    order_service = OrderProcessingService()
    user_service = UserManagementService()
    robust_service = RobustGrpcService()
    
    await order_service.initialize_connections()
    await user_service.setup()
    await robust_service.init()
    
    # Test standard patterns
    user, payment = await order_service.standard_grpc_workflow("Alice", "alice@test.com", 100.0)
    
    # Test advanced patterns  
    users = await order_service.advanced_grpc_patterns(user.id)
    
    # Test streaming
    stream_result = await order_service.streaming_grpc_calls()
    
    # Test sync calls
    sync_results = order_service.sync_grpc_calls(user.id)
    
    # Test management operations
    managed_user = user_service.manage_user(user.id, "get")
    batch_users = user_service.batch_operations([user.id, "user2", "user3"])
    
    # Test error handling
    safe_payment = await robust_service.safe_payment(user.id, 200.0)
    
    logger.info("All comprehensive gRPC tests completed")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())