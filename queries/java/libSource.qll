import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.FlowSources


/**
 * Main predicate for enhanced remote sources.
 * Combines built-in CodeQL sources with modern protocol support.
 */
predicate enhancedSource(DataFlow::Node source) {
  // Built-in CodeQL remote sources (JAX-RS, Spring MVC, Servlets, etc.)
  source instanceof RemoteFlowSource
  or
  // Additional modern sources not covered by built-in
  additionalRemoteSource(source)
}

/**
 * Additional remote sources for modern Java applications.
 */
private predicate additionalRemoteSource(DataFlow::Node source) {
  httpClientSource(source)
  or
  rpcSource(source)
  or
  messageQueueSource(source)
  or
  iotSource(source)
  or
  serviceDiscoverySource(source)
}

/**
 * HTTP client sources - external API responses.
 */
private predicate httpClientSource(DataFlow::Node source) {
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("org.springframework.web.client", "RestTemplate") and
    mc.getMethod().getName() in ["getForObject", "getForEntity", "postForObject", "postForEntity", "exchange", "execute"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("org.springframework.web.reactive.function.client", "WebClient") and
    mc.getMethod().getName() in ["get", "post", "put", "patch", "delete"] and
    source.asExpr() = mc
  )
  or
  // OpenFeign client method calls (return external API responses)
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType() instanceof SpringFeignClient and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.net.http", "HttpClient") and
    mc.getMethod().getName() in ["send", "sendAsync"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("org.apache.http%") and
    mc.getMethod().getName() in ["execute", "doExecute"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("okhttp3", ["OkHttpClient", "Call"]) and
    mc.getMethod().getName() in ["execute", "enqueue"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("cn.hutool.http", "HttpUtil") and
    mc.getMethod().getName() in ["get", "post", "put", "delete", "execute"] and
    source.asExpr() = mc
  )
}

/**
 * Annotation type for @FeignClient and any annotation meta-annotated with @FeignClient.
 */
class SpringFeignClientAnnotation extends AnnotationType {
  SpringFeignClientAnnotation() {
    this.hasQualifiedName("org.springframework.cloud.openfeign", "FeignClient")
    or
    this.getAnAnnotation().getType() instanceof SpringFeignClientAnnotation
  }
}

/**
 * A class or interface annotated, directly or indirectly, as a Spring FeignClient.
 */
class SpringFeignClient extends RefType {
  SpringFeignClient() { 
    exists(Annotation ann |
      ann = this.getAnAnnotation() and
      ann.getType() instanceof SpringFeignClientAnnotation
    )
  }
}

/**
 * RPC framework sources - gRPC, Dubbo.
 */
private predicate rpcSource(DataFlow::Node source) {
  // gRPC client calls
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getName().matches("%BlockingStub") and
    mc.getMethod().isPublic() and
    not mc.getMethod().hasName("newStub") and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getName().matches("%Stub") and
    mc.getMethod().isPublic() and
    not mc.getMethod().hasName("newStub") and
    source.asExpr() = mc
  )
  or
  // gRPC service method parameters (base classes)
  exists(Method method, Parameter param |
    source.asParameter() = param and
    param.getCallable() = method and
    method.getDeclaringType().getName().matches("%ImplBase") and
    method.isPublic()
  )
  or
  // gRPC service method parameters (concrete implementations)
  exists(Method method, Parameter param |
    source.asParameter() = param and
    param.getCallable() = method and
    method.getDeclaringType().getASourceSupertype*().getName().matches("%ImplBase") and
    method.isPublic() and
    method.overrides(_)
  )
  or
  // Dubbo client calls
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasAnnotation() and
    exists(Annotation ann |
      ann = mc.getMethod().getDeclaringType().getAnAnnotation() and
      ann.getType().hasQualifiedName("org.apache.dubbo.config.annotation", "DubboReference")
    ) and
    source.asExpr() = mc
  )
  or
  // Dubbo service method parameters
  exists(Method method, Parameter param |
    source.asParameter() = param and
    param.getCallable() = method and
    exists(Annotation ann |
      ann = method.getDeclaringType().getAnAnnotation() and
      ann.getType().hasQualifiedName("org.apache.dubbo.config.annotation", "DubboService")
    )
  )
}

/**
 * Message queue sources - Kafka, RabbitMQ, JMS.
 */
private predicate messageQueueSource(DataFlow::Node source) {
  // Kafka consumer calls
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("org.apache.kafka.clients.consumer", "KafkaConsumer") and
    mc.getMethod().getName() = "poll" and
    source.asExpr() = mc
  )
  or
  // RabbitMQ consumer calls
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("com.rabbitmq.client", "Channel") and
    mc.getMethod().getName() in ["basicGet", "basicConsume"] and
    source.asExpr() = mc
  )
  or
  // Spring AMQP
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("org.springframework.amqp.%") and
    mc.getMethod().getName() in ["receive", "receiveAndConvert"] and
    source.asExpr() = mc
  )
  or
  // JMS consumer calls
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("javax.jms.%") and
    mc.getMethod().getName() in ["receive", "receiveNoWait"] and
    source.asExpr() = mc
  )
  or
  // Message listener method parameters
  exists(Method method, Parameter param |
    source.asParameter() = param and
    param.getCallable() = method and
    (
      exists(Annotation ann |
        ann = method.getAnAnnotation() and
        ann.getType().hasQualifiedName("org.springframework.kafka.annotation", "KafkaListener")
      )
      or
      exists(Annotation ann |
        ann = method.getAnAnnotation() and
        ann.getType().hasQualifiedName("org.springframework.amqp.rabbit.annotation", "RabbitListener")
      )
      or
      exists(Annotation ann |
        ann = method.getAnAnnotation() and
        ann.getType().hasQualifiedName("org.springframework.jms.annotation", "JmsListener")
      )
    )
  )
}

/**
 * IoT and MQTT sources.
 */
private predicate iotSource(DataFlow::Node source) {
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("org.eclipse.paho.client.mqttv3.%") and
    mc.getMethod().getName() in ["subscribe", "messageArrived"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("javax.websocket.%") and
    mc.getMethod().getName() = "onMessage" and
    source.asExpr() = mc
  )
}

/**
 * Service discovery sources.
 */
private predicate serviceDiscoverySource(DataFlow::Node source) {
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("com.ecwid.consul.%") and
    mc.getMethod().getName() in ["getKVValue", "getAgentServices"] and
    source.asExpr() = mc
  )
  or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getQualifiedName().matches("com.netflix.discovery.%") and
    mc.getMethod().getName() in ["getInstancesById", "getApplication"] and
    source.asExpr() = mc
  )
}