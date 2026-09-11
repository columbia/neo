/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description Lists outbound inter-service communication points together with
 *              the constant channel identifier (URL / topic / gRPC method) that
 *              names the target, for cross-service flow stitching.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import java
import semmle.code.java.dataflow.DataFlow
import libOutBound

/** An outbound inter-service call (any protocol handled by libOutBound). */
predicate outboundCall(MethodCall call, string proto) {
  (restCall(call) or httpClientCall(call)) and proto = "http"
  or
  kafkaCall(call) and proto = "kafka"
  or
  messageQueueCall(call) and proto = "rabbitmq"
  or
  grpcCall(call) and proto = "grpc"
  or
  webSocketCall(call) and proto = "websocket"
  or
  graphqlCall(call) and proto = "graphql"
  or
  dubboCall(call) and proto = "dubbo"
}

/** Best-effort constant string that flows into an argument of `call`. */
string channelOf(MethodCall call) {
  result = call.getAnArgument().(CompileTimeConstantExpr).getStringValue()
  or
  exists(StringLiteral sl |
    DataFlow::localExprFlow(sl, call.getAnArgument()) and
    result = sl.getValue()
  )
}

/** HTTP-ish verb inferred from the callee name; no result when unknown. */
string verbOf(MethodCall call) {
  exists(string n | n = call.getMethod().getName().toLowerCase() |
    (n.matches("%post%") or n.matches("%create%") or n.matches("%publish%") or n.matches("%send%")) and
    result = "POST"
    or
    n.matches("%put%") and not n.matches("%output%") and result = "PUT"
    or
    n.matches("%patch%") and result = "PATCH"
    or
    (n.matches("%delete%") or n.matches("%remove%")) and result = "DELETE"
    or
    (n.matches("%get%") or n.matches("%fetch%") or n.matches("%retrieve%")) and
    not n.matches("%post%") and
    result = "GET"
  )
}

/** verbOf(call) if known, otherwise "". */
bindingset[call]
string verbOrEmpty(MethodCall call) {
  if exists(verbOf(call)) then result = verbOf(call) else result = ""
}

string enclosing(MethodCall call) {
  exists(Callable c | c = call.getEnclosingCallable() |
    result =
      c.getName() + "@" + c.getLocation().getFile().getRelativePath() + ":" +
        c.getLocation().getStartLine().toString()
  )
}

from MethodCall call, string proto, string channel
where
  outboundCall(call, proto) and
  channel = channelOf(call) and
  channel != ""
select call,
  "INTER|" + proto + "|" + verbOrEmpty(call) + "|" + channel + "|" +
    call.getLocation().getFile().getRelativePath() + ":" +
    call.getLocation().getStartLine().toString() + "|" + enclosing(call)
