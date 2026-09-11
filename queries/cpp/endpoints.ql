/**
 * @name Inbound HTTP endpoints and handlers
 * @description cpp-httplib (svr.Get("/x", h)) and Crow (CROW_ROUTE) style route
 *              registrations. Best-effort; the Python heuristic scanner is the
 *              fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import cpp

/** The literal value of *e*, unwrapping the implicit `std::string(const
 *  char*)` conversion the compiler inserts for a string-literal argument. */
string strLiteralValue(Expr e) {
  result = e.(StringLiteral).getValue()
  or
  exists(ConstructorCall cc | cc = e and cc.getTarget().getDeclaringType().getName().matches("basic_string%") |
    result = strLiteralValue(cc.getArgument(0))
  )
}

/** A server route registration: `svr.Get("/x", handler)` — two arguments,
 *  the second being the handler (a lambda or a named callback). */
predicate routeCall(FunctionCall call, string verb, string route) {
  call.getTarget().getName() in ["Get", "Post", "Put", "Delete", "Patch", "Options"] and
  count(call.getAnArgument()) = 2 and
  route = strLiteralValue(call.getArgument(0)) and
  verb = call.getTarget().getName().toUpperCase() and
  route.matches("/%")
}

/** The handler: a lambda passed as the call's last argument, or the call
 *  site itself when it's a named-function reference this pack doesn't
 *  resolve further. */
string handlerRef(FunctionCall call) {
  exists(LambdaExpression f | f = call.getArgument(1) |
    result = "anonymous@" + f.getFile().getRelativePath() + ":" + f.getLocation().getStartLine().toString()
  )
  or
  not call.getArgument(1) instanceof LambdaExpression and
  result = "handler@" + call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString()
}

from FunctionCall call, string verb, string route
where routeCall(call, verb, route)
select call, "ENDPOINT|http|" + verb + "|" + route + "|" + handlerRef(call)
