/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description Outbound axios / fetch / node-http / gRPC / Kafka calls with the
 *              constant channel identifier. Best-effort; the Python heuristic
 *              extractor is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import javascript

string calleeName(DataFlow::CallNode call) { result = call.getCalleeName() }

/** String value of an expression, folding `a + b` of two constant strings and
 *  following a `const X = "..."` initialiser. */
string strValue(Expr e) {
  result = e.getStringValue()
  or
  exists(AddExpr add | add = e |
    result = strValue(add.getLeftOperand()) + strValue(add.getRightOperand())
  )
  or
  exists(Variable v | e = v.getAnAccess() and result = strValue(v.getAnAssignedExpr()))
}

string constArg(DataFlow::CallNode call) {
  result = strValue(call.getAnArgument().asExpr())
  or
  exists(DataFlow::PropWrite pw |
    pw.getBase().getALocalSource() = call.getAnArgument().getALocalSource() and
    (pw.getPropertyName() = "url" or pw.getPropertyName() = "baseURL" or pw.getPropertyName() = "uri") and
    result = strValue(pw.getRhs().asExpr())
  )
}

predicate outboundCall(DataFlow::CallNode call, string proto) {
  exists(string n | n = calleeName(call) |
    (n = "fetch" or n = "get" or n = "post" or n = "put" or n = "delete" or n = "patch" or
     n = "head" or n = "request") and
    proto = "http"
    or
    (n = "send" or n = "sendMessage" or n = "publish") and proto = "kafka"
  )
}

string verbOf(DataFlow::CallNode call) {
  exists(string n | n = calleeName(call) |
    n = "get" and result = "GET"
    or
    n = "post" and result = "POST"
    or
    n = "put" and result = "PUT"
    or
    n = "delete" and result = "DELETE"
    or
    n = "patch" and result = "PATCH"
  )
}

bindingset[call]
string verbOrEmpty(DataFlow::CallNode call) {
  if exists(verbOf(call)) then result = verbOf(call) else result = ""
}

string enclosing(DataFlow::CallNode call) {
  exists(Function f | f = call.getContainer() |
    result = fname(f) + "@" + f.getFile().getRelativePath() + ":" +
        f.getLocation().getStartLine().toString()
  )
}

string fname(Function f) {
  result = f.getName()
  or
  not exists(f.getName()) and result = "anonymous"
}

from DataFlow::CallNode call, string proto, string channel
where outboundCall(call, proto) and channel = constArg(call) and channel != ""
select call,
  "INTER|" + proto + "|" + verbOrEmpty(call) + "|" + channel + "|" +
    call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() + "|" +
    enclosing(call)
