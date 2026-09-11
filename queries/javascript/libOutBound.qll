import javascript
private import semmle.javascript.dataflow.DataFlow

/**
 * Main sink predicate - identifies all outbound data transmission sinks.
 */
predicate outBoundSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    (
      httpClientCall(call) and httpClientSink(call, sink) or
      grpcCall(call) and grpcSink(call, sink) or
      kafkaCall(call) and kafkaSink(call, sink) or
      rabbitMQCall(call) and rabbitMQSink(call, sink) or
      redisCall(call) and redisSink(call, sink) or
      webSocketCall(call) and webSocketSink(call, sink) or
      graphQLCall(call) and graphQLSink(call, sink)
    )
  )
}

/**
 * HTTP Client calls.
 */
predicate httpClientCall(DataFlow::InvokeNode call) {
  // axios calls
  call = API::Node::ofType("axios", ["get", "post", "put", "patch", "delete", "head", "options", "request"]).getACall()
  or
  exists(DataFlow::CallNode cn |
    cn = call and
    cn.getCalleeName() in ["get", "post", "put", "patch", "delete", "head", "options", "request", "fetch"]
  )
  or
  // http/https module
  (
    call.getCalleeName() in ["request", "get"]
  )
}

/**
 * gRPC calls.
 */
predicate grpcCall(DataFlow::InvokeNode call) {
  call.getCalleeName().matches("%Stub%")
  or
  exists(DataFlow::CallNode cn |
    cn = call and
    cn.getCalleeName() in ["write", "end", "onNext"]
  )
}

/**
 * Kafka calls.
 */
predicate kafkaCall(DataFlow::InvokeNode call) {
  call.getCalleeName() in ["send", "sendBatch"]
}

/**
 * RabbitMQ calls.
 */
predicate rabbitMQCall(DataFlow::InvokeNode call) {
  call.getCalleeName() in ["publish", "sendToQueue", "sendMessage"]
}

/**
 * Redis calls.
 */
predicate redisCall(DataFlow::InvokeNode call) {
  call.getCalleeName() in ["set", "setEx", "setNX", "hSet", "hMSet", "publish", "rPush", "lPush",
                            "sAdd", "zAdd", "append", "setbit", "setrange"]
}

/**
 * WebSocket calls.
 */
predicate webSocketCall(DataFlow::InvokeNode call) {
  call.getCalleeName() in ["send", "emit", "broadcast"]
}

/**
 * GraphQL calls.
 */
predicate graphQLCall(DataFlow::InvokeNode call) {
  call.getCalleeName() in ["query", "mutate", "execute", "request"]
}

/**
 * HTTP Client specific sink logic
 */
predicate httpClientSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  // For axios, fetch, etc. - track ALL arguments (URL and body data)
  // GET/DELETE - argument 0 is URL (may contain tainted data)
  (
    call.getCalleeName() in ["get", "delete", "head", "options"] and
    sink = call.getArgument(0)
  )
  or
  // POST/PUT/PATCH - argument 0 is URL, argument 1 is body (track both)
  (
    call.getCalleeName() in ["post", "put", "patch"] and
    sink = call.getAnArgument()
  )
  or
  // Generic request/fetch - track all arguments
  (
    call.getCalleeName() in ["request", "fetch"] and
    sink = call.getAnArgument()
  )
  or
  (
    call.getCalleeName() in ["write"] and
    sink = call.getArgument(0)
  )
}

/**
 * gRPC specific sink logic - message arguments
 */
predicate grpcSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  sink = call.getAnArgument()
}

/**
 * Kafka specific sink logic - only message content, not topic
 */
predicate kafkaSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  sink = call.getAnArgument()
}

/**
 * RabbitMQ specific sink logic - only message content
 */
predicate rabbitMQSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  (
    call.getCalleeName() = "publish" and
    sink = call.getArgument(2)
  )
  or
  (
    call.getCalleeName() = "sendToQueue" and
    sink = call.getArgument(1)
  )
}

/**
 * Redis specific sink logic - data values
 */
predicate redisSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  (
    call.getCalleeName() in ["set", "setEx", "setNX"] and
    sink = call.getArgument([1, 2])
  )
  or
  (
    call.getCalleeName() in ["hSet", "hMSet"] and
    sink = call.getArgument([1, 2])
  )
  or
  (
    call.getCalleeName() = "publish" and
    sink = call.getArgument(1)
  )
  or
  (
    call.getCalleeName() in ["rPush", "lPush", "sAdd", "zAdd"] and
    sink = call.getAnArgument()
  )
}

/**
 * WebSocket specific sink logic - message content
 */
predicate webSocketSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  call.getCalleeName() in ["send", "emit", "broadcast"] and
  sink = call.getAnArgument()
}

/**
 * GraphQL specific sink logic - query/variables
 */
predicate graphQLSink(DataFlow::InvokeNode call, DataFlow::Node sink) {
  sink = call.getAnArgument()
}
