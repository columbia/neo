import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs

// PART 1: OUTBOUND CALL IDENTIFICATION

/**
 * HTTP client calls
 */
predicate httpClientCall(DataFlow::CallCfgNode call) {
  // requests.post/put/patch/delete
  call = API::moduleImport("requests").getMember(["post", "put", "patch", "delete"]).getACall()
  or
  // requests.Session().post/put/patch/delete
  exists(API::CallNode session |
    session = API::moduleImport("requests").getMember("Session").getACall() and
    call = session.getReturn().getMember(["post", "put", "patch", "delete"]).getACall()
  )
  or
  // httpx.post/put/patch/delete
  call = API::moduleImport("httpx").getMember(["post", "put", "patch", "delete"]).getACall()
  or
  // httpx.Client().post/put/patch/delete
  exists(API::CallNode client |
    client = API::moduleImport("httpx").getMember(["Client", "AsyncClient"]).getACall() and
    call = client.getReturn().getMember(["post", "put", "patch", "delete"]).getACall()
  )
  or
  // aiohttp ClientSession
  exists(API::CallNode session |
    session = API::moduleImport("aiohttp").getMember("ClientSession").getACall() and
    call = session.getReturn().getMember(["post", "put", "patch", "delete"]).getACall()
  )
  or
  // urllib.request
  call = API::moduleImport("urllib").getMember("request").getMember(["urlopen", "urlretrieve"]).getACall()
  or
  // Fallback pattern matching with validation
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getAttributeName() in ["post", "put", "patch", "delete"] and
    (exists(call.getArg(0)) or exists(call.getArgByName("url")))
  )
}

/**
 * gRPC stub calls
 */
predicate grpcStubCall(DataFlow::CallCfgNode call) {
  // grpc.insecure_channel or grpc.secure_channel
  call = API::moduleImport("grpc").getMember(["insecure_channel", "secure_channel"]).getACall()
  or
  // grpc.aio channels
  call = API::moduleImport("grpc").getMember("aio").getMember(["insecure_channel", "secure_channel"]).getACall()
  or
  // Stub method calls - pattern matching
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getObject().toString().regexpMatch(".*[sS]tub.*") and
    exists(call.getArg(_))
  )
}

/**
 * Kafka producer calls
 */
predicate kafkaProducerCall(DataFlow::CallCfgNode call) {
  // kafka-python: KafkaProducer().send()
  exists(API::CallNode producer |
    producer = API::moduleImport("kafka").getMember("KafkaProducer").getACall() and
    call = producer.getReturn().getMember(["send", "send_and_wait", "flush"]).getACall()
  )
  or
  // confluent-kafka: Producer().produce()
  exists(API::CallNode producer |
    producer = API::moduleImport("confluent_kafka").getMember("Producer").getACall() and
    call = producer.getReturn().getMember(["produce", "poll", "flush"]).getACall()
  )
  or
  // aiokafka
  exists(API::CallNode producer |
    producer = API::moduleImport("aiokafka").getMember("AIOKafkaProducer").getACall() and
    call = producer.getReturn().getMember(["send", "send_and_wait", "flush"]).getACall()
  )
  or
  // Fallback pattern matching
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getAttributeName() in ["send", "produce"] and
    attr.getObject().toString().regexpMatch(".*[pP]roducer.*")
  )
}

/**
 * Redis calls
 */
predicate redisCall(DataFlow::CallCfgNode call) {
  // redis.Redis().operations
  exists(API::CallNode redis |
    redis = API::moduleImport("redis").getMember("Redis").getACall() and
    call = redis.getReturn().getMember(["set", "hset", "lpush", "rpush", "sadd", "zadd", "publish"]).getACall()
  )
  or
  // aioredis operations
  exists(API::CallNode redis |
    redis = API::moduleImport("aioredis").getMember(["Redis", "create_redis", "create_redis_pool"]).getACall() and
    call = redis.getReturn().getMember(["set", "hset", "lpush", "rpush", "sadd", "zadd", "publish"]).getACall()
  )
  or
  // Fallback pattern matching
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getAttributeName() in ["set", "hset", "lpush", "rpush", "publish"] and
    attr.getObject().toString().regexpMatch(".*[rR]edis.*")
  )
}

/**
 * Message queue calls
 */
predicate messageQueueCall(DataFlow::CallCfgNode call) {
  // RabbitMQ pika
  exists(API::CallNode connection, API::CallNode channel |
    connection = API::moduleImport("pika").getMember("BlockingConnection").getACall() and
    channel = connection.getReturn().getMember("channel").getACall() and
    call = channel.getReturn().getMember("basic_publish").getACall()
  )
  or
  // AWS SQS
  exists(API::CallNode client |
    client = API::moduleImport("boto3").getMember("client").getACall() and
    call = client.getReturn().getMember(["send_message", "send_message_batch"]).getACall()
  )
  or
  // Google Pub/Sub
  exists(API::CallNode publisher |
    publisher = API::moduleImport("google").getMember("cloud").getMember("pubsub_v1").getMember("PublisherClient").getACall() and
    call = publisher.getReturn().getMember("publish").getACall()
  )
  or
  // Fallback pattern matching
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getAttributeName() in ["publish", "send_message", "basic_publish"]
  )
}

/**
 * Celery task calls
 */
predicate celeryTaskCall(DataFlow::CallCfgNode call) {
  // Celery app.send_task
  exists(API::CallNode app |
    app = API::moduleImport("celery").getMember("Celery").getACall() and
    call = app.getReturn().getMember("send_task").getACall()
  )
  or
  // Pattern matching for .delay() and .apply_async()
  exists(DataFlow::AttrRead attr |
    call.getFunction() = attr and
    attr.getAttributeName() in ["delay", "apply_async"]
  )
}

/**
 * execute_privileged_operation calls
 */
predicate executePrivilegedOperationCall(DataFlow::CallCfgNode call) {
  call.getFunction().toString() = "execute_privileged_operation"
  or
  call.getFunction().(DataFlow::AttrRead).getAttributeName() = "execute_privileged_operation"
}

// PART 2: OUTBOUND SINKS

/**
 * Main outbound sink predicate
 */
predicate outBoundSink(DataFlow::Node sink) {
  exists(DataFlow::CallCfgNode call |
    (
      httpClientCall(call) and
      sink = call.getArgByName(["json", "data", "files"])
      or
      grpcStubCall(call) and
      (sink = call or sink = call.getArg(_))
      or
      kafkaProducerCall(call) and
      sink = call.getArgByName(["value", "key"])
      or
      redisCall(call) and
      sink = call.getArgByName(["value", "data"])
      or
      messageQueueCall(call) and
      sink = call.getArgByName(["body", "message", "data", "MessageBody"])
      or
      celeryTaskCall(call) and
      sink = call.getArg(_)
      or
      executePrivilegedOperationCall(call) and
      sink = call.getArg(0)
    )
  )
}

// PART 3: TAINT STEPS

/**
 * Main taint step predicate for outbound data flow
 */
predicate outboundTaintStep(DataFlow::Node pred, DataFlow::Node succ) {
  argumentToReceiverStep(pred, succ)
  or
  receiverToReturnStep(pred, succ)
  or
  attributeAccessStep(pred, succ)
  or
  jsonSerializationStep(pred, succ)
  or
  methodCallStep(pred, succ)
  or
  constructorStep(pred, succ)
  or
  outboundCallTaintStep(pred, succ)
}

/**
 * Taint step: argument flows to receiver object
 */
predicate argumentToReceiverStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call, DataFlow::AttrRead attr |
    call.getFunction() = attr and
    pred = call.getArg(_) and
    succ = attr.getObject() and
    attr.getAttributeName() in [
      "set", "add", "append", "insert", "update", "put",
      "send", "publish", "produce", "emit", "write"
    ]
  )
}

/**
 * Taint step: receiver object flows to return value
 */
predicate receiverToReturnStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call, DataFlow::AttrRead attr |
    call.getFunction() = attr and
    pred = attr.getObject() and
    succ = call and
    attr.getAttributeName() in [
      "json", "dict", "serialize", "encode", "dumps",
      "to_string", "to_dict", "to_json"
    ]
  )
}

/**
 * Taint step: attribute access preserves taint
 */
predicate attributeAccessStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::AttrRead attr |
    pred = attr.getObject() and
    succ = attr and
    attr.getAttributeName() in [
      "id", "name", "email", "data", "value", "content", "message",
      "body", "payload", "text", "user_id", "amount"
    ]
  )
}

/**
 * Taint step: JSON/serialization operations preserve taint
 */
predicate jsonSerializationStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call |
    pred = call.getArg(0) and
    succ = call and
    call.getFunction().(DataFlow::AttrRead).getAttributeName() in ["dumps", "json", "serialize", "encode"]
  )
}

/**
 * Taint step: method calls that transform data
 */
predicate methodCallStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call, DataFlow::AttrRead attr |
    call.getFunction() = attr and
    pred = attr.getObject() and
    succ = call and
    attr.getAttributeName() in [
      "copy", "transform", "convert", "process", "format"
    ]
  )
}

/**
 * Taint step: constructor calls with tainted arguments
 */
predicate constructorStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call |
    pred = call.getArg(_) and
    succ = call and
    call.getFunction().toString().regexpMatch("[A-Z].*")
  )
}

/**
 * Taint step: data flows through outbound calls
 */
predicate outboundCallTaintStep(DataFlow::Node pred, DataFlow::Node succ) {
  exists(DataFlow::CallCfgNode call |
    (
      httpClientCall(call) and
      pred = call.getArgByName(["json", "data", "files"]) and
      succ = call
      or
      grpcStubCall(call) and
      pred = call.getArg(_) and
      succ = call
      or
      kafkaProducerCall(call) and
      pred = call.getArgByName(["value", "key"]) and
      succ = call
      or
      redisCall(call) and
      pred = call.getArgByName(["value", "data"]) and
      succ = call
      or
      messageQueueCall(call) and
      pred = call.getArgByName(["body", "message", "data"]) and
      succ = call
      or
      celeryTaskCall(call) and
      pred = call.getArg(_) and
      succ = call
      or
      executePrivilegedOperationCall(call) and
      pred = call.getArg(0) and
      succ = call
    )
  )
}