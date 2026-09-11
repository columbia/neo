import csharp
import semmle.code.csharp.dataflow.DataFlow

// PART 1: OUTBOUND CALL IDENTIFICATION

/**
 * HttpClient calls (System.Net.Http.HttpClient).
 */
predicate httpClientCall(MethodCall call) {
  call.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Net.Http.HttpClient") and
  call.getTarget().getName() in ["GetAsync", "GetStringAsync", "GetByteArrayAsync",
                                  "GetStreamAsync", "PostAsync", "PutAsync", "PatchAsync",
                                  "DeleteAsync", "SendAsync", "PostAsJsonAsync", "PutAsJsonAsync"]
  or
  // IHttpClientFactory-created clients via extension methods
  call.getTarget().getName() in ["PostAsJsonAsync", "PutAsJsonAsync", "PatchAsJsonAsync"] and
  call.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Net.Http.%")
  or
  // RestSharp / Refit common patterns
  call.getTarget().getName() in ["Execute", "ExecuteAsync", "ExecutePost", "ExecutePostAsync"] and
  call.getTarget().getDeclaringType().getName().matches("%Client%")
}

/**
 * gRPC client stub calls.
 */
predicate grpcClientCall(MethodCall call) {
  call.getTarget().getDeclaringType().getABaseType*().getName().matches("%ClientBase%")
  or
  call.getTarget().getDeclaringType().getABaseType*().getName().matches("%GrpcClient%")
}

/**
 * Message queue producer calls (Azure Service Bus, RabbitMQ, MassTransit, etc.).
 */
predicate messageQueueCall(MethodCall call) {
  // Azure Service Bus
  call.getTarget().getDeclaringType().getName().matches("%ServiceBusSender%") and
  call.getTarget().getName() in ["SendMessageAsync", "SendMessagesAsync"]
  or
  // RabbitMQ
  call.getTarget().getDeclaringType().getName().matches("%IModel%") and
  call.getTarget().getName() = "BasicPublish"
  or
  // MassTransit
  call.getTarget().getDeclaringType().getName().matches("%IPublishEndpoint%") and
  call.getTarget().getName() in ["Publish", "PublishAsync"]
  or
  call.getTarget().getDeclaringType().getName().matches("%ISendEndpoint%") and
  call.getTarget().getName() in ["Send", "SendAsync"]
  or
  // Generic Kafka producer
  call.getTarget().getDeclaringType().getName().matches("%IProducer%") and
  call.getTarget().getName() in ["Produce", "ProduceAsync"]
}

// PART 2: OUTBOUND SINKS

/**
 * Main outbound sink predicate.
 */
predicate outBoundSink(DataFlow::Node sink) {
  exists(MethodCall call |
    httpClientCall(call) and
    sink.asExpr() = call.getAnArgument()
    or
    grpcClientCall(call) and
    sink.asExpr() = call.getAnArgument()
    or
    messageQueueCall(call) and
    sink.asExpr() = call.getAnArgument()
  )
}
