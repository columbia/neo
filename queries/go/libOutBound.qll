import go
import semmle.go.dataflow.DataFlow

/**
 * Main outbound sink predicate - identifies all outbound data transmission sinks.
 */
predicate outBoundSink(DataFlow::Node sink) {
  httpClientSink(sink)
  or
  grpcClientSink(sink)
  or
  kafkaProducerSink(sink)
  or
  rabbitmqProducerSink(sink)
  or
  redisPublisherSink(sink)
  or
  executePrivilegedOperationSink(sink)
}

/**
 * HTTP client sinks - outbound HTTP requests.
 */
predicate httpClientSink(DataFlow::Node sink) {
  // Resty client - request body/data arguments
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/go-resty/resty/v2", "Request", 
      ["SetBody", "SetBodyJsonString", "SetBodyBytes", "SetFormData", "SetMultipartFormData"]) and
    sink = call.getArgument(0)
  )
  or
  // net/http client - request body (package-level functions)
  exists(DataFlow::CallNode call |
    (
      call.getTarget().hasQualifiedName("net/http", ["Post", "PostForm"]) and
      sink = call.getArgument(2)
    ) or
    (
      call.getTarget().hasQualifiedName("net/http", "NewRequest") and
      sink = call.getArgument(2)
    )
  )
  or
  // net/http client - request URL (path / query carry the target and often
  // carry tainted identifiers): http.Get/Head/Post/PostForm(url, ...)
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("net/http", ["Get", "Head", "Post", "PostForm"]) and
    sink = call.getArgument(0)
  )
  or
  // http.NewRequest(method, url, body) / NewRequestWithContext(ctx, method, url, body)
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("net/http", "NewRequest") and sink = call.getArgument(1)
    or
    call.getTarget().hasQualifiedName("net/http", "NewRequestWithContext") and
    sink = call.getArgument(2)
  )
  or
  // net/http Client - request body + URL (method calls)
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("net/http", "Client", ["Post", "PostForm"]) and
    sink = call.getArgument(2)
    or
    call.getTarget().hasQualifiedName("net/http", "Client", ["Get", "Head", "Post", "PostForm"]) and
    sink = call.getArgument(0)
  )
  or
  // res ty / gorequest / sling style: a method on a *Client / *Request whose
  // name sets the URL or issues the request
  exists(DataFlow::MethodCallNode call, Method m |
    m = call.getTarget() and
    m.getReceiverType().getName().toLowerCase().matches(["%client%", "%request%"]) and
    m.getName() = ["Get", "Post", "Put", "Patch", "Delete", "Head", "SetPathParams",
                   "SetQueryString", "SetQueryParams", "R", "URL", "Send", "Execute", "Do"] and
    sink = call.getAnArgument()
  )
  or
  // Gin response methods
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/gin-gonic/gin", "Context", 
      ["JSON", "XML", "YAML", "String", "Data"]) and
    sink = call.getAnArgument()
  )
}

/**
 * gRPC client sinks - outbound RPC calls.
 */
predicate grpcClientSink(DataFlow::Node sink) {
  // gRPC client method calls - request message argument
  exists(DataFlow::MethodCallNode call, Method m |
    m = call.getTarget() and
    m.getName().regexpMatch("(Get|Create|Update|Delete|List|Process|Stream).*") and
    m.getReceiverType().getName().matches("%Client") and
    sink = call.getArgument(1)  // First arg is context, second is request
  )
  or
  // gRPC stub calls (user-defined)
  exists(DataFlow::MethodCallNode call, Method m |
    m = call.getTarget() and
    m.getReceiverType().getName().matches("%Stub") and
    sink = call.getAnArgument()
  )
}

/**
 * Kafka producer sinks - message publishing.
 */
predicate kafkaProducerSink(DataFlow::Node sink) {
  // kafka.Writer.WriteMessages
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/segmentio/kafka-go", "Writer", "WriteMessages") and
    sink = call.getAnArgument()
  )
  or
  // Message field writes - Value field
  exists(Write write, Field f |
    f.hasQualifiedName("github.com/segmentio/kafka-go", "Message", "Value") and
    write.writesField(_, f, sink)
  )
}

/**
 * RabbitMQ producer sinks - message publishing.
 */
predicate rabbitmqProducerSink(DataFlow::Node sink) {
  // Channel.Publish / PublishWithContext
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/rabbitmq/amqp091-go", "Channel", 
      ["Publish", "PublishWithContext"]) and
    sink = call.getArgument([5, 6])  // Publishing argument (body)
  )
  or
  // Publishing field writes - Body field
  exists(Write write, Field f |
    f.hasQualifiedName("github.com/rabbitmq/amqp091-go", "Publishing", "Body") and
    write.writesField(_, f, sink)
  )
}

/**
 * Redis publisher sinks - pub/sub and data operations.
 */
predicate redisPublisherSink(DataFlow::Node sink) {
  // Redis publish operations
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/redis/go-redis/v9", "Client", 
      ["Publish", "Set", "HSet", "LPush", "RPush", "SAdd", "ZAdd"]) and
    sink = call.getAnArgument()
  )
}

/**
 * Execute privileged operation sinks.
 */
predicate executePrivilegedOperationSink(DataFlow::Node sink) {
  exists(DataFlow::CallNode call, Function f |
    call.getTarget() = f and
    f.getName() = "executePrivilegedOperation" and
    sink = call.getArgument(0)
  )
  or
  exists(DataFlow::CallNode call, Function f |
    call.getTarget() = f and
    f.getName().regexpMatch("(?i).*execute.*privileged.*") and
    sink = call.getAnArgument()
  )
}

/**
 * Taint steps for outbound data flow.
 */
predicate outboundTaintStep(DataFlow::Node pred, DataFlow::Node succ) {
  // Method calls that transform data
  exists(DataFlow::MethodCallNode call |
    call.getTarget().getName() in ["String", "Bytes", "Marshal", "Unmarshal", "Encode", "Decode"] and
    pred = call.getReceiver() and
    succ = call.getResult()
  )
  or
  // JSON marshaling
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("encoding/json", "Marshal") and
    pred = call.getArgument(0) and
    succ = call.getResult(0)
  )
  or
  // JSON unmarshaling - propagate taint from source to destination
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("encoding/json", "Unmarshal") and
    pred = call.getArgument(0) and  // Source bytes
    succ = call.getArgument(1)      // Destination pointer
  )
  or
  // JSON Decoder.Decode - propagate taint from decoder to destination
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("encoding/json", "Decoder", "Decode") and
    pred = call.getReceiver() and   // The decoder (contains the source data)
    succ = call.getArgument(0)      // Destination pointer
  )
  or
  // JSON NewDecoder - propagate taint from reader to decoder
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("encoding/json", "NewDecoder") and
    pred = call.getArgument(0) and  // io.Reader (e.g., resp.Body)
    succ = call.getResult()         // Decoder
  )
  or
  // String conversion
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("fmt", ["Sprint", "Sprintf", "Sprintln"]) and
    pred = call.getAnArgument() and
    succ = call.getResult()
  )
  or
  // Field reads preserve taint
  exists(DataFlow::FieldReadNode read |
    pred = read.getBase() and
    succ = read
  )
  or
  // io.ReadAll - propagate taint from reader to bytes
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("io", "ReadAll") and
    pred = call.getArgument(0) and
    succ = call.getResult(0)
  )
  or
  // bytes.NewBuffer - propagate taint from bytes to buffer
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("bytes", "NewBuffer") and
    pred = call.getArgument(0) and
    succ = call.getResult()
  )
  or
  // Struct field writes - propagate taint from value to the struct
  exists(Write write |
    write.writesField(pred, _, succ)
  )
  or
  // Composite literal field initialization - taint flows from field values to the composite
  exists(CompositeLit lit, KeyValueExpr kv |
    lit.getAnElement() = kv and
    pred = DataFlow::exprNode(kv.getValue()) and
    succ = DataFlow::exprNode(lit)
  )
}