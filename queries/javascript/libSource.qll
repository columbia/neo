import javascript
private import semmle.javascript.dataflow.DataFlow
private import semmle.javascript.security.dataflow.RemoteFlowSources

/**
 * Main predicate for enhanced remote sources.
 * Combines built-in CodeQL sources with modern protocol support.
 */
predicate enhancedSource(DataFlow::Node source) {
  // Built-in CodeQL remote sources (Express, HTTP servers, etc.)
  source instanceof RemoteFlowSource
  or
  // Additional modern sources not covered by built-in
  additionalRemoteSource(source)
}

/**
 * Additional remote sources for modern JavaScript/Node.js applications.
 */
private predicate additionalRemoteSource(DataFlow::Node source) {
  httpClientSource(source)
  or
  rpcSource(source)
  or
  messageQueueSource(source)
}

/**
 * HTTP client sources - external API responses.
 */
private predicate httpClientSource(DataFlow::Node source) {
  // axios, fetch, http client responses
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() in ["get", "post", "put", "patch", "delete", "head", "options", "request", "fetch"] and
    source = call
  )
}

/**
 * RPC framework sources - gRPC, GraphQL.
 */
private predicate rpcSource(DataFlow::Node source) {
  // gRPC client calls
  exists(DataFlow::InvokeNode call |
    call.getCalleeName().matches("%Stub%") and
    source = call
  )
  or
  // GraphQL resolvers - parameters are external data
  exists(Function resolver, Parameter param |
    (
      resolver.getName().matches("%resolver%") or
      resolver.getName().matches("%Query%") or
      resolver.getName().matches("%Mutation%")
    ) and
    param = resolver.getParameter([1, 2, 3]) and
    source = DataFlow::parameterNode(param)
  )
}

/**
 * Message queue sources - Kafka, RabbitMQ, Redis.
 */
private predicate messageQueueSource(DataFlow::Node source) {
  // Kafka, RabbitMQ, Redis consumer callbacks
  exists(DataFlow::FunctionNode callback, Parameter param |
    param = callback.getFunction().getParameter(0) and
    source = DataFlow::parameterNode(param)
  )
}
