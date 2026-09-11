/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description Outbound HttpClient / RestSharp / gRPC / message-bus calls with
 *              the constant channel identifier. Best-effort; the Python
 *              heuristic extractor is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import csharp

/** String value of an expression: a literal/const, `a + b` folded (keeping the
 *  constant prefix when the tail is a runtime value), or a field/variable
 *  reached through its initialiser. */
string strValue(Expr e) {
  result = e.getValue()
  or
  exists(AddExpr add | add = e |
    result = strValue(add.getLeftOperand()) + strValue(add.getRightOperand())
    or
    result = strValue(add.getLeftOperand())
  )
  or
  exists(Field f | e = f.getAnAccess() | result = strValue(f.getInitializer()))
  or
  exists(LocalVariable v | e = v.getAnAccess() | result = strValue(v.getInitializer()))
}

string constStringArg(MethodCall call) {
  exists(Expr e | e = call.getAnArgument() |
    result = strValue(e)
    or
    exists(ObjectCreation oc | oc = e | result = strValue(oc.getAnArgument())) // new Uri("...")
  )
}

predicate outboundCall(MethodCall call, string proto, string verb) {
  exists(string n | n = call.getTarget().getName() |
    n in ["GetAsync", "GetStringAsync", "GetFromJsonAsync"] and proto = "http" and verb = "GET"
    or
    n in ["PostAsync", "PostAsJsonAsync"] and proto = "http" and verb = "POST"
    or
    n in ["PutAsync", "PutAsJsonAsync"] and proto = "http" and verb = "PUT"
    or
    n in ["PatchAsync", "PatchAsJsonAsync"] and proto = "http" and verb = "PATCH"
    or
    n in ["DeleteAsync"] and proto = "http" and verb = "DELETE"
    or
    n in ["SendAsync"] and proto = "http" and verb = ""
    or
    n in ["ExecuteAsync", "Execute"] and proto = "http" and verb = ""
    or
    n in ["PublishAsync", "SendAsync", "Send"] and
    call.getTarget().getDeclaringType().getName().matches(["%Bus%", "%ServiceBus%", "%Producer%"]) and
    proto = "kafka" and
    verb = ""
  )
}

string enclosing(MethodCall call) {
  exists(Callable c | c = call.getEnclosingCallable() |
    result =
      c.getName() + "@" + call.getFile().getRelativePath() + ":" +
        c.getLocation().getStartLine().toString()
  )
}

from MethodCall call, string proto, string verb, string channel
where outboundCall(call, proto, verb) and channel = constStringArg(call) and channel != ""
select call,
  "INTER|" + proto + "|" + verb + "|" + channel + "|" +
    call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() + "|" +
    enclosing(call)
