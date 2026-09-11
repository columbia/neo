import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs
private import semmle.python.dataflow.new.RemoteFlowSources

/**
 * Additional remote sources for modern Python applications.
 */
predicate enhancedSource(DataFlow::Node source) {

  source instanceof RemoteFlowSource //or

//   httpClientSource(source)
  or
  rpcSource(source)
  or
  messageQueueSource(source)
//   or
//   iotSource(source)
//   or
//   serviceDiscoverySource(source)
}

/**
 * HTTP client sources - external API responses.
 */
predicate httpClientSource(DataFlow::Node source) {
  // requests library
  source = API::moduleImport("requests").getMember(["get", "post", "put", "delete", "patch", "head", "options"]).getACall()
  or
  source = API::moduleImport("requests").getMember("request").getACall()
  or
  source = API::moduleImport("requests").getMember("Session").getReturn().getMember(["get", "post", "put", "delete", "patch"]).getACall()
  or
  
  // httpx (async HTTP client)
  source = API::moduleImport("httpx").getMember(["get", "post", "put", "delete", "patch", "head", "options"]).getACall()
  or
  source = API::moduleImport("httpx").getMember("Client").getReturn().getMember(["get", "post", "put", "delete", "patch"]).getACall()
  or
  source = API::moduleImport("httpx").getMember("AsyncClient").getReturn().getMember(["get", "post", "put", "delete", "patch"]).getACall()
  or
  
  // aiohttp (async HTTP client)
  source = API::moduleImport("aiohttp").getMember("ClientSession").getReturn().getMember(["get", "post", "put", "delete", "patch", "head", "options"]).getACall()
  or
  source = API::moduleImport("aiohttp").getMember("request").getACall()
  or
  
  // urllib (standard library)
  source = API::moduleImport("urllib.request").getMember("urlopen").getACall()
  or
  source = API::moduleImport("urllib.request").getMember("Request").getACall()
  or
  
  // urllib3
  source = API::moduleImport("urllib3").getMember("PoolManager").getReturn().getMember("request").getACall()
  or
  source = API::moduleImport("urllib3").getMember("HTTPSConnectionPool").getReturn().getMember(["request", "urlopen"]).getACall()
  or
  
  // tornado HTTP client
  source = API::moduleImport("tornado.httpclient").getMember("HTTPClient").getReturn().getMember("fetch").getACall()
  or
  source = API::moduleImport("tornado.httpclient").getMember("AsyncHTTPClient").getReturn().getMember("fetch").getACall()
  or
  
  // treq (Twisted HTTP client)
  source = API::moduleImport("treq").getMember(["get", "post", "put", "delete", "patch", "head"]).getACall()
}

/**
 * RPC sources - remote procedure call responses.
 */
predicate rpcSource(DataFlow::Node source) {
  // gRPC client calls
  exists(Call call, Attribute attr |
    call.getFunc() = attr and
    attr.getName().matches("%_pb2_grpc") and
    source.asExpr() = call
  )
  or
  source = API::moduleImport("grpc").getMember("insecure_channel").getACall()
  or
  source = API::moduleImport("grpc").getMember("secure_channel").getACall()
  or
  
  // XML-RPC client
  exists(Call call, Attribute attr, Call serverProxy |
    source.asExpr() = call and
    call.getFunc() = attr and
    attr.getObject() = serverProxy and
    serverProxy.getFunc().(Attribute).getName() = "ServerProxy"
  )
  or
  
  // JSON-RPC client
  source = API::moduleImport("jsonrpcclient").getMember("request").getACall()
  or
  source = API::moduleImport("jsonrpcclient").getMember("HTTPClient").getReturn().getMember("request").getACall()
  or
  
  // Apache Thrift
  source = API::moduleImport("thrift.transport.THttpClient").getMember("THttpClient").getACall()
  or
  source = API::moduleImport("thrift.transport.TSocket").getMember("TSocket").getACall()
  or
  
  // Pyro (Python Remote Objects)
  source = API::moduleImport("Pyro4").getMember("Proxy").getACall()
  or
  source = API::moduleImport("Pyro5.api").getMember("Proxy").getACall()
}

/**
 * Message queue sources - external message consumption.
 */
predicate messageQueueSource(DataFlow::Node source) {
  // Apache Kafka
  source = API::moduleImport("kafka").getMember("KafkaConsumer").getReturn().getMember(["poll", "__iter__"]).getACall()
  or
  source = API::moduleImport("confluent_kafka").getMember("Consumer").getReturn().getMember(["poll", "consume"]).getACall()
  or
  source = API::moduleImport("aiokafka").getMember("AIOKafkaConsumer").getReturn().getMember(["getone", "getmany"]).getACall()
  or
  
  // RabbitMQ / AMQP
  source = API::moduleImport("pika").getMember("BlockingConnection").getReturn().getMember("channel").getReturn().getMember("basic_get").getACall()
  or
  source = API::moduleImport("aio_pika").getMember("connect").getReturn().getMember("channel").getReturn().getMember("get_queue").getReturn().getMember("get").getACall()
  or
  source = API::moduleImport("kombu").getMember("Consumer").getReturn().getMember("receive").getACall()
  or
  
  // Redis Pub/Sub
  source = API::moduleImport("redis").getMember("Redis").getReturn().getMember("pubsub").getReturn().getMember(["get_message", "listen"]).getACall()
  or
  source = API::moduleImport("aioredis").getMember("Redis").getReturn().getMember("pubsub").getReturn().getMember(["get_message", "subscribe"]).getACall()
  or
  
  // Apache Pulsar
  source = API::moduleImport("pulsar").getMember("Client").getReturn().getMember("subscribe").getReturn().getMember("receive").getACall()
  or
  
  // AWS SQS
  exists(Call boto3_call, Call sqs_call |
    boto3_call = API::moduleImport("boto3").getMember("client").getACall().asExpr() and
    sqs_call.getFunc().(Attribute).getObject() = boto3_call and
    sqs_call.getFunc().(Attribute).getName() in ["receive_message", "receive_message_batch"] and
    source.asExpr() = sqs_call
  )
  or
  
  // Google Cloud Pub/Sub
  source = API::moduleImport("google.cloud.pubsub_v1").getMember("SubscriberClient").getReturn().getMember("pull").getACall()
  or
  
  // Azure Service Bus
  source = API::moduleImport("azure.servicebus").getMember("ServiceBusClient").getReturn().getMember("get_queue_receiver").getReturn().getMember("receive_messages").getACall()
}

/**
 * IoT sources - IoT device communications.
 */
predicate iotSource(DataFlow::Node source) {
  // MQTT
  exists(Call call, Attribute attr, Call clientCall |
    source.asExpr() = call and
    call.getFunc() = attr and
    attr.getName() = "on_message" and
    attr.getObject() = clientCall and
    clientCall.getFunc().(Attribute).getName() = "Client"
  )
  or
  source = API::moduleImport("asyncio_mqtt").getMember("Client").getReturn().getMember("messages").getACall()
  or
  source = API::moduleImport("gmqtt").getMember("Client").getReturn().getMember("on_message").getACall()
  or
  
  // CoAP (Constrained Application Protocol)
  source = API::moduleImport("aiocoap").getMember("Context").getReturn().getMember("request").getACall()
  or
  source = API::moduleImport("coapthon.client.helperclient").getMember("HelperClient").getReturn().getMember("get").getACall()
  or
  
  // Modbus
  source = API::moduleImport("pymodbus.client.sync").getMember("ModbusTcpClient").getReturn().getMember(["read_coils", "read_discrete_inputs", "read_holding_registers"]).getACall()
  or
  source = API::moduleImport("pymodbus.client.asynchronous.tcp").getMember("AsyncModbusTCPClient").getReturn().getMember("read_holding_registers").getACall()
  or
  
  // OPC UA
  source = API::moduleImport("opcua").getMember("Client").getReturn().getMember(["get_node", "read_value"]).getACall()
  or
  
  // LoRaWAN
  source = API::moduleImport("lorawan").getMember("LoRaWAN").getReturn().getMember("receive").getACall()
  or
  
  // Zigbee
  source = API::moduleImport("zigpy").getMember("Application").getReturn().getMember("receive_message").getACall()
}

/**
 * Service discovery sources - external service registry responses.
 */
predicate serviceDiscoverySource(DataFlow::Node source) {
  // Consul
  source = API::moduleImport("consul").getMember("Consul").getReturn().getMember("kv").getMember("get").getACall()
  or
  source = API::moduleImport("consul").getMember("Consul").getReturn().getMember("health").getMember("service").getACall()
  or
  source = API::moduleImport("consul").getMember("Consul").getReturn().getMember("catalog").getMember("service").getACall()
  or
  
  // etcd
  source = API::moduleImport("etcd3").getMember("client").getReturn().getMember(["get", "get_prefix", "watch", "watch_prefix"]).getACall()
  or
  source = API::moduleImport("python_etcd").getMember("Client").getReturn().getMember(["read", "get"]).getACall()
  or
  
  // Zookeeper
  source = API::moduleImport("kazoo.client").getMember("KazooClient").getReturn().getMember(["get", "get_children"]).getACall()
  or
  
  // Eureka
  source = API::moduleImport("py_eureka_client.eureka_client").getMember("get_application").getACall()
  or
  source = API::moduleImport("py_eureka_client.eureka_client").getMember("get_applications").getACall()
  or
  
  // Kubernetes API
  source = API::moduleImport("kubernetes.client").getMember("CoreV1Api").getReturn().getMember(["list_service", "read_service"]).getACall()
  or
  source = API::moduleImport("kubernetes.client").getMember("AppsV1Api").getReturn().getMember(["list_deployment", "read_deployment"]).getACall()
  or
  
  // Docker API
  source = API::moduleImport("docker").getMember("from_env").getReturn().getMember("containers").getMember(["list", "get"]).getACall()
  or
  source = API::moduleImport("docker").getMember("DockerClient").getReturn().getMember("services").getMember(["list", "get"]).getACall()
  or
  
  // Nacos
  source = API::moduleImport("nacos").getMember("NacosClient").getReturn().getMember(["get_config", "list_naming_instance"]).getACall()
}

/**
 * Gets the source category for classification.
 */
string getRemoteSourceCategory(DataFlow::Node source) {
  httpClientSource(source) and result = "HTTP_CLIENT"
  or
  rpcSource(source) and result = "RPC"
  or
  messageQueueSource(source) and result = "MESSAGE_QUEUE"
  or
  iotSource(source) and result = "IOT"
  or
  serviceDiscoverySource(source) and result = "SERVICE_DISCOVERY"
}

/**
 * Gets the specific technology/framework name based on module imports.
 */
string getRemoteSourceTechnology(DataFlow::Node source) {
  // HTTP clients
  source = API::moduleImport("requests").getMember(_).getACall() and result = "requests"
  or
  source = API::moduleImport("httpx").getMember(_).getACall() and result = "httpx"
  or
  source = API::moduleImport("aiohttp").getMember(_).getACall() and result = "aiohttp"
  or
  source = API::moduleImport("urllib.request").getMember(_).getACall() and result = "urllib"
  or
  source = API::moduleImport("urllib3").getMember(_).getACall() and result = "urllib3"
  or
  source = API::moduleImport("tornado.httpclient").getMember(_).getACall() and result = "tornado"
  or
  source = API::moduleImport("treq").getMember(_).getACall() and result = "treq"
  or
  
  // RPC
  source = API::moduleImport("grpc").getMember(_).getACall() and result = "gRPC"
  or
  source = API::moduleImport("jsonrpcclient").getMember(_).getACall() and result = "JSON-RPC"
  or
  source = API::moduleImport("Pyro4").getMember(_).getACall() and result = "Pyro4"
  or
  source = API::moduleImport("Pyro5.api").getMember(_).getACall() and result = "Pyro5"
  or
  
  // Message queues
  source = API::moduleImport("kafka").getMember(_).getACall() and result = "Apache Kafka"
  or
  source = API::moduleImport("confluent_kafka").getMember(_).getACall() and result = "Confluent Kafka"
  or
  source = API::moduleImport("aiokafka").getMember(_).getACall() and result = "aiokafka"
  or
  source = API::moduleImport("pika").getMember(_).getACall() and result = "RabbitMQ (pika)"
  or
  source = API::moduleImport("aio_pika").getMember(_).getACall() and result = "RabbitMQ (aio_pika)"
  or
  source = API::moduleImport("redis").getMember(_).getACall() and result = "Redis"
  or
  source = API::moduleImport("aioredis").getMember(_).getACall() and result = "Redis (aioredis)"
  or
  
  // IoT
  source = API::moduleImport("aiocoap").getMember(_).getACall() and result = "CoAP"
  or
  source = API::moduleImport("opcua").getMember(_).getACall() and result = "OPC UA"
  or
  
  // Service Discovery
  source = API::moduleImport("consul").getMember(_).getACall() and result = "Consul"
  or
  source = API::moduleImport("etcd3").getMember(_).getACall() and result = "etcd"
  or
  source = API::moduleImport("kubernetes.client").getMember(_).getACall() and result = "Kubernetes"
  or
  source = API::moduleImport("docker").getMember(_).getACall() and result = "Docker"
}