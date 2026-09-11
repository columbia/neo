/**
 * @name Inbound HTTP endpoints and handlers
 * @description Express / Koa-router / Fastify route registrations.
 *              Best-effort; the Python heuristic scanner is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import javascript

string mname(DataFlow::MethodCallNode call) { result = call.getMethodName() }

predicate routeCall(DataFlow::MethodCallNode call, string verb, string route) {
  route = call.getArgument(0).getStringValue() and
  route.matches("/%") and
  exists(string m | m = mname(call) |
    m = "get" and verb = "GET"
    or
    m = "post" and verb = "POST"
    or
    m = "put" and verb = "PUT"
    or
    m = "delete" and verb = "DELETE"
    or
    m = "patch" and verb = "PATCH"
    or
    (m = "all" or m = "use" or m = "route") and verb = ""
  )
}

string fname(Function f) {
  f.getName() != "" and result = f.getName()
  or
  not f.getName() != "" and result = "anonymous"
}

/** The route handler function: an inline `(req,res)=>{}` / `function(){}` as the
 *  last argument, or one reached through a local variable. */
Function handlerFn(DataFlow::MethodCallNode call) {
  result = call.getLastArgument().asExpr()
  or
  result = call.getLastArgument().getALocalSource().(DataFlow::FunctionNode).getFunction()
}

string handlerName(DataFlow::MethodCallNode call) {
  exists(Function f | f = handlerFn(call) |
    result = fname(f) + "@" + f.getFile().getRelativePath() + ":" +
        f.getLocation().getStartLine().toString()
  )
  or
  not exists(handlerFn(call)) and
  result = "anonymous@" + call.getFile().getRelativePath() + ":" +
      call.getLocation().getStartLine().toString()
}

from DataFlow::MethodCallNode call, string verb, string route
where routeCall(call, verb, route)
select call, "ENDPOINT|http|" + verb + "|" + route + "|" + handlerName(call)
