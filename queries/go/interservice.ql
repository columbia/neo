/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description Outbound HTTP / gRPC / Kafka / RabbitMQ calls together with the
 *              constant channel identifier (URL / topic) that names the target.
 *              Best-effort; the Python heuristic extractor is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import go

string calleeName(DataFlow::CallNode call) { result = call.getTarget().getName() }

/** The callee is a method on a type that looks like an HTTP client (resty,
 *  gorequest, sling, req, …) rather than, say, url.Values.Get. */
predicate onHttpClientType(DataFlow::CallNode call) {
  exists(Method m | m = call.getTarget() |
    m.getReceiverType().getName().toLowerCase().matches(["%client%", "%request%", "%resty%"])
  )
}

predicate outboundCall(DataFlow::CallNode call, string proto) {
  proto = "http" and
  (
    call.getTarget().hasQualifiedName("net/http",
      ["Get", "Post", "PostForm", "Head", "NewRequest", "NewRequestWithContext"])
    or
    call.getTarget().(Method).hasQualifiedName("net/http", "Client",
      ["Get", "Post", "PostForm", "Head", "Do"])
    or
    onHttpClientType(call) and
    calleeName(call) = ["Get", "Post", "Put", "Patch", "Delete", "Head", "Do", "Send", "Execute"]
  )
  or
  proto = "kafka" and calleeName(call) = ["SendMessage", "SendMessages", "WriteMessages"]
  or
  proto = "rabbitmq" and calleeName(call) = ["Publish", "PublishWithContext"]
  or
  proto = "grpc" and calleeName(call).matches("Invoke%")
}

/** The node that holds the channel (URL / topic) for this outbound call. */
DataFlow::Node channelArg(DataFlow::CallNode call) {
  exists(string n | n = calleeName(call) |
    (n = "Get" or n = "Post" or n = "PostForm" or n = "Head" or n = "Publish" or
     n = "PublishWithContext" or n = "Send" or n = "Execute" or n = "Do") and
    result = call.getArgument(0)
    or
    n = "NewRequest" and result = call.getArgument(1)
    or
    (n = "NewRequestWithContext" or n.matches("Invoke%")) and result = call.getArgument(2)
    or
    (n = "SendMessage" or n = "SendMessages" or n = "WriteMessages") and
    result = call.getAnArgument()
  )
}

/** String value of an expression: a literal / const, `a + b` folded, keeping the
 *  constant prefix when the tail is a runtime value. */
string strValueExpr(Expr e) {
  result = e.getStringValue()
  or
  exists(AddExpr add | add = e |
    result = strValueExpr(add.getLeftOperand()) + strValueExpr(add.getRightOperand())
    or
    result = strValueExpr(add.getLeftOperand())
  )
}

/** Resolve a channel node to a string, following local data flow back to the
 *  concatenation / literal that produced it. */
string channelString(DataFlow::CallNode call) {
  exists(DataFlow::Node src |
    (src = channelArg(call) or DataFlow::localFlow(src, channelArg(call))) and
    result = strValueExpr(src.asExpr())
  )
}

string verbOf(DataFlow::CallNode call) {
  exists(string n | n = calleeName(call) |
    n = "Get" and result = "GET"
    or
    (n = "Post" or n = "PostForm") and result = "POST"
    or
    n = "Head" and result = "HEAD"
  )
}

bindingset[call]
string verbOrEmpty(DataFlow::CallNode call) {
  if exists(verbOf(call)) then result = verbOf(call) else result = ""
}

string enclosing(DataFlow::CallNode call) {
  exists(FuncDef fd | fd = call.asExpr().getEnclosingFunction() |
    result =
      enclosingName(fd) + "@" + call.getFile().getRelativePath() + ":" +
        fd.getLocation().getStartLine().toString()
  )
  or
  not exists(call.asExpr().getEnclosingFunction()) and
  result = "@" + call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString()
}

string enclosingName(FuncDef fd) {
  result = fd.(FuncDecl).getName()
  or
  not fd instanceof FuncDecl and result = "anonymous"
}

from DataFlow::CallNode call, string proto, string channel
where
  outboundCall(call, proto) and
  channel = channelString(call) and
  channel != "" and
  (proto != "http" or channel.regexpMatch("(?i)(https?://|/|[a-z0-9.-]+\\.[a-z]{2,}).*"))
select call,
  "INTER|" + proto + "|" + verbOrEmpty(call) + "|" + channel + "|" +
    call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() + "|" +
    enclosing(call)
