/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description Lists outbound inter-service communication points together with
 *              the constant channel identifier that names the target.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs
import libOutBound

predicate outboundCall(DataFlow::CallCfgNode call, string proto) {
  httpClientCall(call) and proto = "http"
  or
  grpcStubCall(call) and proto = "grpc"
  or
  kafkaProducerCall(call) and proto = "kafka"
  or
  messageQueueCall(call) and proto = "rabbitmq"
}

/** An argument expression of the call (positional or keyword). */
Expr callArg(DataFlow::CallCfgNode call) {
  result = call.getArg(_).asExpr() or result = call.getArgByName(_).asExpr()
}

/**
 * Constant string that names the channel: a literal argument, a literal
 * anywhere in the argument expression (`base + "/path"`), a literal that flows
 * to the argument, or a module/local constant referenced by the argument
 * (`URL = "http://..."; requests.post(URL + "/x")`).
 */
string channelOf(DataFlow::CallCfgNode call) {
  exists(StrConst s |
    s = callArg(call).getASubExpression*() or
    DataFlow::localFlow(DataFlow::exprNode(s), call.getArg(_))
  |
    result = s.getText()
  )
  or
  exists(Name ref, Variable var, AssignStmt a, StrConst s |
    ref = callArg(call).getASubExpression*() and
    ref.getVariable() = var and
    a.getATarget().(Name).getVariable() = var and
    a.getValue() = s and
    result = s.getText()
  )
}

string calleeName(DataFlow::CallCfgNode call) {
  result = call.getFunction().asCfgNode().(NameNode).getId()
  or
  result = call.getFunction().asCfgNode().(AttrNode).getName()
}

/** HTTP-ish verb inferred from the callee name; no result when unknown. */
string verbOf(DataFlow::CallCfgNode call) {
  exists(string n | n = calleeName(call).toLowerCase() |
    (n.matches("%post%") or n.matches("%publish%") or n.matches("%send%")) and result = "POST"
    or
    n.matches("%put%") and result = "PUT"
    or
    n.matches("%patch%") and result = "PATCH"
    or
    n.matches("%delete%") and result = "DELETE"
    or
    n.matches("%get%") and not n.matches("%post%") and result = "GET"
  )
}

bindingset[call]
string verbOrEmpty(DataFlow::CallCfgNode call) {
  if exists(verbOf(call)) then result = verbOf(call) else result = ""
}

string enclosing(DataFlow::CallCfgNode call) {
  exists(Function f | f.contains(call.asExpr()) |
    result =
      f.getName() + "@" + f.getLocation().getFile().getRelativePath() + ":" +
        f.getLocation().getStartLine().toString()
  )
  or
  not exists(Function f | f.contains(call.asExpr())) and result = ""
}

from DataFlow::CallCfgNode call, string proto, string channel
where
  outboundCall(call, proto) and
  channel = channelOf(call) and
  channel != "" and
  // not a route decorator (@app.post("/x")) or its own registration
  not exists(Function f | f.getADecorator() = call.asExpr()) and
  not exists(Class c | c.getADecorator() = call.asExpr())
select call,
  "INTER|" + proto + "|" + verbOrEmpty(call) + "|" + channel + "|" +
    call.getLocation().getFile().getRelativePath() + ":" +
    call.getLocation().getStartLine().toString() + "|" + enclosing(call)
