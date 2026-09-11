import csharp
import semmle.code.csharp.dataflow.DataFlow
import semmle.code.csharp.security.dataflow.flowsources.Remote

/**
 * Main predicate for enhanced remote sources.
 * Combines built-in CodeQL ASP.NET Core sources with modern protocol support.
 */
predicate enhancedSource(DataFlow::Node source) {
  // Built-in CodeQL remote sources (ASP.NET Core controller params, HttpRequest, etc.)
  source instanceof RemoteFlowSource
  or
  rpcSource(source)
  or
  messageQueueSource(source)
  or
  heuristicParamSource(source)
  or
  requestCollectionReadSource(source)
}

/**
 * A read from a request-shaped key/value collection: ``NameValueCollection``
 * (``HttpListenerRequest.QueryString`` / classic ``Request.Form`` /
 * ``Request.QueryString``), ``IFormCollection``, ``IQueryCollection``,
 * ``IHeaderDictionary`` — covers services that parse a request without
 * going through the ASP.NET Core MVC binding CodeQL's RemoteFlowSource models.
 */
private predicate requestCollectionReadSource(DataFlow::Node source) {
  exists(IndexerCall ic |
    ic.getQualifier().getType().getName()
        .matches(["NameValueCollection", "%FormCollection", "%QueryCollection",
                 "%HeaderDictionary", "%ParamCollection"]) and
    source.asExpr() = ic
  )
}

/**
 * Request-shaped parameter names (``body``, ``role``, ``userId``, …) on a
 * public method, for services that pass untrusted data as a plain argument
 * rather than through an attribute CodeQL's ASP.NET model recognises (an
 * internal RPC handler, a queue consumer invoked by reflection, a bare
 * request-handling method in a framework this pack doesn't model yet).
 */
private predicate heuristicParamSource(DataFlow::Node source) {
  exists(Parameter p |
    p.getCallable().(Modifiable).isPublic() and
    p.getName().toLowerCase()
        .regexpMatch(".*(request|req|body|input|param|query|form|payload|" +
          "role|username|userid|user_id|email).*") and
    source.asExpr().(ParameterRead).getTarget() = p
  )
}

/**
 * gRPC service method parameters.
 */
private predicate rpcSource(DataFlow::Node source) {
  // Parameters of methods in gRPC service implementations
  exists(Parameter p, Method m |
    m.getAParameter() = p and
    (
      m.getDeclaringType().getABaseType*().getName().matches("%ServiceBase") or
      m.getDeclaringType().getABaseType*().getName().matches("%GrpcService%") or
      m.getAnAttribute().getType().getName().matches("Grpc%")
    ) and
    source.asExpr().(ParameterRead).getTarget() = p
  )
}

/**
 * Message queue consumer parameters (Azure Service Bus, RabbitMQ, etc.).
 */
private predicate messageQueueSource(DataFlow::Node source) {
  exists(Parameter p, Method m |
    m.getAParameter() = p and
    (
      p.getType().getFullyQualifiedName().matches("%.ServiceBusReceivedMessage") or
      p.getType().getFullyQualifiedName().matches("%.BasicDeliverEventArgs") or
      p.getType().getFullyQualifiedName().matches("%.IMessage%") or
      m.getAnAttribute().getType().getName().matches("%ServiceBusTrigger%") or
      m.getAnAttribute().getType().getName().matches("%QueueTrigger%")
    ) and
    source.asExpr().(ParameterRead).getTarget() = p
  )
}
