/**
 * @name Inbound HTTP endpoints and handlers
 * @description Route registrations for net/http, gin, echo, chi, gorilla/mux.
 *              Best-effort; the Python heuristic scanner is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import go

string routeArg(DataFlow::CallNode call) {
  exists(StringLit lit | lit = call.getArgument(0).asExpr() | result = lit.getValue())
}

predicate routeCall(DataFlow::CallNode call, string verb) {
  exists(string m | m = call.getTarget().getName() |
    (m = "GET" or m = "POST" or m = "PUT" or m = "DELETE" or m = "PATCH" or
     m = "HEAD" or m = "OPTIONS") and verb = m
    or
    (m = "Handle" or m = "HandleFunc" or m = "Any" or m = "Match" or m = "ANY") and verb = ""
  )
}

/** The handler function passed to a route registration: a named function
 *  reference (`mux.HandleFunc("/x", h)`) or an inline `func(...) { … }`. */
FuncDef handlerFn(DataFlow::CallNode call) {
  exists(DataFlow::Node last | last = call.getArgument(count(call.getAnArgument()) - 1) |
    result = last.asExpr().(FuncLit)
    or
    result.(FuncDecl).getName() = last.asExpr().(Ident).getName()
  )
}

string handlerRef(DataFlow::CallNode call) {
  exists(FuncDef f | f = handlerFn(call) |
    result = handlerName(f) + "@" + f.getLocation().getFile().getRelativePath() + ":" +
        f.getLocation().getStartLine().toString()
  )
  or
  not exists(handlerFn(call)) and
  result = "handler@" + call.getFile().getRelativePath() + ":" +
      call.getLocation().getStartLine().toString()
}

string handlerName(FuncDef f) {
  result = f.(FuncDecl).getName()
  or
  not f instanceof FuncDecl and result = "anonymous"
}

from DataFlow::CallNode call, string verb, string route
where routeCall(call, verb) and route = routeArg(call) and route.matches("/%")
select call, "ENDPOINT|http|" + verb + "|" + route + "|" + handlerRef(call)
