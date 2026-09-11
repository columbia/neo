import java
import semmle.code.java.dataflow.DataFlow

/**
 * Main sink predicate - identifies all outbound data transmission sinks.
 */
predicate outBoundSink(DataFlow::Node sink) {
  exists(MethodCall call |
    call.getNumArgument() > 0 and
    (
      httpClientCall(call) and httpClientSink(call, sink) or
      restCall(call) and restSink(call, sink) or
      kafkaCall(call) and kafkaSink(call, sink) or
      grpcCall(call) and grpcSink(call, sink) or
      messageQueueCall(call) and messageQueueSink(call, sink) or
      webSocketCall(call) and webSocketSink(call, sink) or
      graphqlCall(call) and graphqlSink(call, sink) or
      dubboCall(call) and dubboSink(call, sink)
    )
  )
}

/**
 * HTTP Client calls.
 */
predicate httpClientCall(MethodCall call) {
  // JDK HttpClient
  call.getMethod().getDeclaringType().hasQualifiedName("java.net.http", ["HttpClient", "HttpRequest$BodyPublishers"]) and
  call.getMethod().getName() in ["send", "sendAsync", "ofString", "ofByteArray", "ofInputStream"]
  or
  // Apache HttpClient
  call.getMethod().getDeclaringType().getQualifiedName().matches("org.apache.http.%") and
  call.getMethod().getName() in ["execute", "setEntity"]
  or
  // OkHttp
  call.getMethod().getDeclaringType().hasQualifiedName("okhttp3", ["RequestBody", "Request$Builder"]) and
  call.getMethod().getName() in ["create", "post", "put", "patch", "delete"]
  or
  // Hutool HTTP
  call.getMethod().getDeclaringType().hasQualifiedName("cn.hutool.http", "HttpUtil") and
  call.getMethod().getName() in ["get", "post", "put", "delete", "patch", "head", "options"]
}

/**
 * REST API calls.
 */
predicate restCall(MethodCall call) {
  // Spring RestTemplate
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.web.client", "RestTemplate") and
  call.getMethod().getName() in [
    "getForObject", "getForEntity",
    "postForObject", "postForEntity", 
    "put", "patchForObject", 
    "exchange", 
    "execute"
  ]
  or
  // Spring WebClient
  call.getMethod().getDeclaringType().getQualifiedName().matches("org.springframework.web.reactive.function.client.%") and
  call.getMethod().getName() in ["bodyValue", "body", "syncBody"]
  or
  // Feign Client
  exists(Parameter param, int i |
    call.getMethod().getDeclaringType().getAnAnnotation().getType().hasQualifiedName("org.springframework.cloud.openfeign", "FeignClient") and
    param = call.getMethod().getParameter(i) and
    param.getAnAnnotation().getType().hasQualifiedName("org.springframework.web.bind.annotation", "RequestBody")
  )
  or
  call.getMethod().getDeclaringType().getAnAnnotation().getType().hasQualifiedName("org.springframework.cloud.openfeign", "FeignClient")
}

/**
 * gRPC calls.
 */
predicate grpcCall(MethodCall call) {
  // gRPC stubs
  call.getMethod().getDeclaringType().getName().matches("%Stub")
  or
  // gRPC streaming
  call.getMethod().getDeclaringType().getQualifiedName().matches("io.grpc.stub.%") and
  call.getMethod().getName() in ["onNext", "onCompleted", "onError"]
  or
  // gRPC channel
  call.getMethod().getDeclaringType().hasQualifiedName("io.grpc", "Channel") and
  call.getMethod().getName() = "newCall"
  or
  // Protobuf messages
  call.getMethod().getDeclaringType().getASourceSupertype*().getQualifiedName().matches("com.google.protobuf.%") and
  call.getMethod().getName().matches("set%")
}

/**
 * Kafka calls.
 */
predicate kafkaCall(MethodCall call) {
  // Spring Kafka - Fixed to handle generic types
  call.getMethod().getDeclaringType().getPackage().getName() = "org.springframework.kafka.core" and
  call.getMethod().getDeclaringType().getName().matches("KafkaTemplate%") and
  call.getMethod().getName() in ["send", "sendDefault", "executeInTransaction"]
  or
  // Kafka Producer
  call.getMethod().getDeclaringType().hasQualifiedName("org.apache.kafka.clients.producer", "KafkaProducer") and
  call.getMethod().getName() = "send"
  or
  // Spring Cloud Stream
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.cloud.stream.function", "StreamBridge") and
  call.getMethod().getName() = "send"
  or
  // Kafka Streams
  call.getMethod().getDeclaringType().hasQualifiedName("org.apache.kafka.streams.kstream", "KStream") and
  call.getMethod().getName() in ["to", "through"]
  or
  // Generic Kafka
  call.getMethod().getDeclaringType().getQualifiedName().matches("org.apache.kafka.%") and
  call.getMethod().getName() in ["send", "produce", "publish", "write"]
}

/**
 * Message Queue calls.
 */
predicate messageQueueCall(MethodCall call) {
  // RabbitMQ
  call.getMethod().getDeclaringType().hasQualifiedName("com.rabbitmq.client", "Channel") and
  call.getMethod().getName() = "basicPublish"
  or
  // Spring AMQP
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.amqp.rabbit.core", "RabbitTemplate") and
  call.getMethod().getName() in ["send", "convertAndSend"]
  or
  // JMS
  call.getMethod().getDeclaringType().getQualifiedName().matches("javax.jms.%") and
  call.getMethod().getName() = "send"
  or
  // Redis Pub/Sub
  call.getMethod().getDeclaringType().hasQualifiedName("redis.clients.jedis", "Jedis") and
  call.getMethod().getName() = "publish"
}

/**
 * WebSocket calls.
 */
predicate webSocketCall(MethodCall call) {
  // Java-WebSocket
  call.getMethod().getDeclaringType().getQualifiedName().matches("org.java_websocket.%") and
  call.getMethod().getName() in ["send", "sendText", "sendBinary"]
  or
  // Spring WebSocket
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.web.socket", "WebSocketSession") and
  call.getMethod().getName() = "sendMessage"
  or
  // Netty WebSocket
  call.getMethod().getDeclaringType().getQualifiedName().matches("io.netty.handler.codec.http.websocketx.%") and
  call.getMethod().getName() in ["writeAndFlush", "write"]
}

/**
 * GraphQL calls.
 */
predicate graphqlCall(MethodCall call) {
  // Spring GraphQL
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.graphql.client", "GraphQlClient") and
  call.getMethod().getName() in ["document", "documentName", "variable", "variables"]
  or
  // GraphQL Java client
  call.getMethod().getDeclaringType().hasQualifiedName("com.graphql-java-kickstart.client", "GraphQLClient") and
  call.getMethod().getName() in ["execute", "executeAsync"]
  or
  // HTTP GraphQL (RestTemplate with /graphql endpoint)
  call.getMethod().getDeclaringType().hasQualifiedName("org.springframework.web.client", "RestTemplate") and
  call.getMethod().getName() in ["postForObject", "postForEntity", "exchange"] and
  exists(StringLiteral url | 
    url = call.getArgument(0) and 
    url.getValue().toLowerCase().matches("%/graphql%")
  )
  or
  // GraphQL builders
  call.getMethod().getDeclaringType().getName().toLowerCase().matches(["%graphql%", "%gql%", "%mutation%", "%query%"]) and
  call.getMethod().getName() in ["query", "mutation", "subscription", "variable", "variables"]
}

/**
 * Dubbo calls.
 */
predicate dubboCall(MethodCall call) {
  // @DubboReference annotated services
  exists(Field field |
    call.getQualifier() = field.getAnAccess() and
    field.getAnAnnotation().getType().hasQualifiedName("org.apache.dubbo.config.annotation", "DubboReference")
  )
  or
  // Dubbo GenericService
  call.getMethod().getDeclaringType().hasQualifiedName("org.apache.dubbo.rpc.service", "GenericService") and
  call.getMethod().getName() = "$invoke"
  or
  // Dubbo async calls
  call.getMethod().getDeclaringType().getQualifiedName().matches("org.apache.dubbo.rpc.%") and
  call.getMethod().getName().matches("%Async")
}

/**
 * HTTP Client specific sink logic
 */
predicate httpClientSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument() and
  not sink.asExpr() instanceof TypeLiteral and
  (
    // JDK HttpClient - exclude HttpRequest, keep body data
    (call.getMethod().getName() in ["send", "sendAsync"] and
     sink.asExpr() = call.getArgument(0)) or
    
    // Body publishers - all arguments are data
    (call.getMethod().getName() in ["ofString", "ofByteArray", "ofInputStream"] and
     sink.asExpr() = call.getAnArgument()) or
     
    // OkHttp - exclude builders, keep data
    (call.getMethod().getName() in ["create", "post", "put", "patch"] and
     sink.asExpr() = call.getAnArgument())
  )
}

/**
 * REST API specific sink logic
 */
predicate restSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument() and
  not sink.asExpr() instanceof TypeLiteral and
  (
    // RestTemplate - exclude response type (last argument for most methods)
    (call.getMethod().getName() in ["getForObject", "postForObject"] and
     sink.asExpr() = call.getArgument([0..call.getNumArgument()-2])) or
    
    // RestTemplate exchange - exclude response type
    (call.getMethod().getName() = "exchange" and
     sink.asExpr() = call.getArgument([0..call.getNumArgument()-2])) or
     
    // WebClient - all arguments are data
    (call.getMethod().getName() in ["bodyValue", "body", "syncBody"] and
     sink.asExpr() = call.getAnArgument()) or
     
    // Feign Client - all arguments are data
    (call.getMethod().getDeclaringType().hasAnnotation("org.springframework.cloud.openfeign", "FeignClient") and
     sink.asExpr() = call.getAnArgument())
  )
}

/**
 * Kafka specific sink logic - only message content, not topic
 */
predicate kafkaSink(MethodCall call, DataFlow::Node sink) {
  (
    // KafkaTemplate.send(topic, message) - only message (argument 1)
    (call.getMethod().getName() = "send" and
     call.getNumArgument() >= 2 and
     sink.asExpr() = call.getArgument([1..call.getNumArgument()-1])) or
     
    // KafkaTemplate.sendDefault(message) - message (argument 0)  
    (call.getMethod().getName() = "sendDefault" and
     sink.asExpr() = call.getArgument(0)) or
     
    // Other Kafka methods - all arguments
    (call.getMethod().getName() in ["executeInTransaction"] and
     sink.asExpr() = call.getAnArgument())
  )
}

/**
 * gRPC specific sink logic - only message arguments
 */
predicate grpcSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument() and
  (
    // gRPC stub calls - all arguments are protobuf messages
    (call.getMethod().getDeclaringType().getName().matches("%Stub") and
     sink.asExpr() = call.getAnArgument()) or
     
    // gRPC streaming - only message data
    (call.getMethod().getName() in ["onNext"] and
     sink.asExpr() = call.getArgument(0)) or
     
    // Channel calls - exclude method descriptor
    (call.getMethod().getName() = "newCall" and
     sink.asExpr() = call.getArgument(1))
  )
}

/**
 * Message Queue specific sink logic - only message content
 */
predicate messageQueueSink(MethodCall call, DataFlow::Node sink) {
  (
    // RabbitMQ basicPublish - exclude exchange/routing key, keep message
    (call.getMethod().getName() = "basicPublish" and
     call.getNumArgument() >= 4 and
     sink.asExpr() = call.getArgument([3..call.getNumArgument()-1])) or
     
    // RabbitTemplate - only message content
    (call.getMethod().getName() in ["send", "convertAndSend"] and
     sink.asExpr() = call.getArgument([1..call.getNumArgument()-1])) or
     
    // JMS - only message content
    (call.getMethod().getName() = "send" and
     sink.asExpr() = call.getArgument([0..0])) or
     
    // Redis publish - only message content
    (call.getMethod().getName() = "publish" and
     sink.asExpr() = call.getArgument(1))
  )
}

/**
 * WebSocket specific sink logic - only message content
 */
predicate webSocketSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument() and
  call.getMethod().getName() in ["send", "sendText", "sendBinary", "sendMessage", "writeAndFlush", "write"]
}

/**
 * GraphQL specific sink logic - only query/variables
 */
predicate graphqlSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument() and
  call.getMethod().getName() in ["document", "documentName", "variable", "variables", "execute", "executeAsync", "query", "mutation", "subscription"]
}

/**
 * Dubbo specific sink logic - all arguments (method parameters)
 */
predicate dubboSink(MethodCall call, DataFlow::Node sink) {
  sink.asExpr() = call.getAnArgument()
}