import go
import semmle.go.dataflow.DataFlow

/**
 * Enhanced remote sources for Go microservices.
 */
predicate enhancedSource(DataFlow::Node source) {
  httpServerSource(source)
  or
  httpClientSource(source)
  or
  grpcServerSource(source)
  or
  grpcClientSource(source)
  or
  kafkaConsumerSource(source)
  or
  rabbitmqConsumerSource(source)
  or
  redisSubscriberSource(source)
}

/**
 * HTTP server sources - incoming requests.
 */
predicate httpServerSource(DataFlow::Node source) {
  // Gin framework - context parameters
  exists(Function f, Parameter p |
    p = f.getAParameter() and
    p.getType().(DefinedType).hasQualifiedName("github.com/gin-gonic/gin", "Context") and
    source = DataFlow::parameterNode(p)
  )
  or
  // Gin context methods that return request data
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/gin-gonic/gin", "Context", 
      ["Param", "Query", "PostForm", "GetHeader", "GetRawData", "ShouldBindJSON"]) and
    source = call.getResult()
  )
  or
  // net/http handlers - request parameter (ServeHTTP method implementing Handler)
  exists(Method m, Parameter p |
    m.getReceiverType().implements("net/http", "Handler") and
    m.getName() = "ServeHTTP" and
    p = m.getParameter(1) and
    p.getType().(PointerType).getBaseType().(DefinedType).hasQualifiedName("net/http", "Request") and
    source = DataFlow::parameterNode(p)
  )
  or
  // net/http HandlerFunc - function that matches the signature (named or anonymous)
  exists(FuncDef f, Parameter p |
    f.getNumParameter() = 2 and
    f.getParameter(0).getType().(DefinedType).hasQualifiedName("net/http", "ResponseWriter") and
    p = f.getParameter(1) and
    p.getType().(PointerType).getBaseType().(DefinedType).hasQualifiedName("net/http", "Request") and
    source = DataFlow::parameterNode(p)
  )
  or
  // http.Request field accesses
  exists(DataFlow::FieldReadNode field |
    field.getField().hasQualifiedName("net/http", "Request",
      ["Body", "Header", "Form", "PostForm", "URL"]) and
    source = field
  )
  or
  // http.Request method call return values (FormValue, PostFormValue, etc.)
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("net/http", "Request",
      ["FormValue", "PostFormValue", "FormFile", "UserAgent", "Referer", "Cookie", "Cookies"]) and
    source = call.getResult()
  )
  or
  // gorilla/mux Vars (URL path params)
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("github.com/gorilla/mux", "Vars") and
    source = call.getResult()
  )
}

/**
 * HTTP client sources - external API responses.
 */
predicate httpClientSource(DataFlow::Node source) {
  // Resty client responses
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/go-resty/resty/v2", "Client", 
      ["Get", "Post", "Put", "Patch", "Delete", "R"]) and
    source = call.getResult()
  )
  or
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/go-resty/resty/v2", "Request", 
      ["Get", "Post", "Put", "Patch", "Delete", "Execute"]) and
    source = call.getResult()
  )
  or
  // net/http client responses - package-level functions
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("net/http", ["Get", "Post", "PostForm"]) and
    source = call.getResult(0)
  )
  or
  // net/http Client methods - Get, Post, Head, etc.
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("net/http", "Client",
      ["Do", "Get", "Post", "PostForm", "Head"]) and
    source = call.getResult(0)
  )
  or
  // http.Response field accesses
  exists(DataFlow::FieldReadNode field |
    field.getField().hasQualifiedName("net/http", "Response", "Body") and
    source = field
  )
}

/**
 * gRPC server sources - incoming RPC requests.
 */
predicate grpcServerSource(DataFlow::Node source) {
  // gRPC service method parameters (request messages)
  exists(Method m, Parameter p |
    m.getName().regexpMatch("(Get|Create|Update|Delete|List|Process|Stream).*") and
    p = m.getParameter(1) and
    (
      p.getType().getName().matches("%Request") or
      p.getType().getName().matches("%Req")
    ) and
    source = DataFlow::parameterNode(p)
  )
  or
  // Context parameter in gRPC methods
  exists(Method m, Parameter p |
    p = m.getParameter(0) and
    p.getType().(DefinedType).hasQualifiedName("context", "Context") and
    m.getName().regexpMatch("(Get|Create|Update|Delete|List|Process|Stream).*") and
    source = DataFlow::parameterNode(p)
  )
}

/**
 * gRPC client sources - RPC responses.
 */
predicate grpcClientSource(DataFlow::Node source) {
  // gRPC client method calls
  exists(DataFlow::MethodCallNode call, Method m |
    m = call.getTarget() and
    m.getName().regexpMatch("(Get|Create|Update|Delete|List|Process|Stream).*") and
    m.getReceiverType().getName().matches("%Client") and
    source = call.getResult(0)
  )
}

/**
 * Kafka consumer sources - incoming messages.
 */
predicate kafkaConsumerSource(DataFlow::Node source) {
  // kafka.Reader.ReadMessage / FetchMessage
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/segmentio/kafka-go", "Reader", 
      ["ReadMessage", "FetchMessage"]) and
    source = call.getResult(0)
  )
  or
  // Message field accesses
  exists(DataFlow::FieldReadNode field |
    field.getField().hasQualifiedName("github.com/segmentio/kafka-go", "Message", 
      ["Value", "Key", "Headers"]) and
    source = field
  )
  or
  // Consumer iteration pattern - range over messages
  exists(RangeStmt range |
    range.getDomain().getType().(ChanType).getElementType().(DefinedType).hasQualifiedName(
      "github.com/segmentio/kafka-go", "Message") and
    source = DataFlow::exprNode(range.getValue())
  )
}

/**
 * RabbitMQ consumer sources - incoming messages.
 */
predicate rabbitmqConsumerSource(DataFlow::Node source) {
  // Channel.Consume
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/rabbitmq/amqp091-go", "Channel", "Consume") and
    source = call.getResult(0)
  )
  or
  // Delivery field accesses
  exists(DataFlow::FieldReadNode field |
    field.getField().hasQualifiedName("github.com/rabbitmq/amqp091-go", "Delivery", 
      ["Body", "Headers", "RoutingKey"]) and
    source = field
  )
  or
  // Consumer channel iteration - range over deliveries
  exists(RangeStmt range |
    range.getDomain().getType().(ChanType).getElementType().(DefinedType).hasQualifiedName(
      "github.com/rabbitmq/amqp091-go", "Delivery") and
    source = DataFlow::exprNode(range.getValue())
  )
}

/**
 * Redis subscriber sources - pub/sub messages.
 */
predicate redisSubscriberSource(DataFlow::Node source) {
  // PubSub.Channel / Receive
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/redis/go-redis/v9", "PubSub", 
      ["Channel", "Receive", "ReceiveMessage"]) and
    source = call.getResult(0)
  )
  or
  // Message field accesses
  exists(DataFlow::FieldReadNode field |
    field.getField().hasQualifiedName("github.com/redis/go-redis/v9", "Message", 
      ["Payload", "Channel"]) and
    source = field
  )
}

/**
 * Gets the source category for classification.
 */
string getRemoteSourceCategory(DataFlow::Node source) {
  httpServerSource(source) and result = "HTTP_SERVER"
  or
  httpClientSource(source) and result = "HTTP_CLIENT"
  or
  grpcServerSource(source) and result = "GRPC_SERVER"
  or
  grpcClientSource(source) and result = "GRPC_CLIENT"
  or
  kafkaConsumerSource(source) and result = "KAFKA_CONSUMER"
  or
  rabbitmqConsumerSource(source) and result = "RABBITMQ_CONSUMER"
  or
  redisSubscriberSource(source) and result = "REDIS_SUBSCRIBER"
}