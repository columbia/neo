/**
 * @name Inbound HTTP endpoints and handlers
 * @description ASP.NET attribute-routed controller actions ([HttpGet("x")],
 *              [Route("x")]) and minimal-API app.MapGet/MapPost(...). Best
 *              effort; the Python heuristic scanner is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import csharp

predicate httpMethodAttr(Attribute a, string verb) {
  exists(string n | n = a.getType().getName() |
    n = "HttpGetAttribute" and verb = "GET"
    or
    n = "HttpPostAttribute" and verb = "POST"
    or
    n = "HttpPutAttribute" and verb = "PUT"
    or
    n = "HttpDeleteAttribute" and verb = "DELETE"
    or
    n = "HttpPatchAttribute" and verb = "PATCH"
    or
    n = "RouteAttribute" and verb = ""
  )
}

string attrRoute(Attribute a) {
  result = a.getArgument(0).getValue()
  or
  not exists(a.getArgument(0)) and result = ""
}

string classPrefix(Method m) {
  exists(Attribute ca | ca = m.getDeclaringType().getAnAttribute() and httpMethodAttr(ca, _) |
    result = attrRoute(ca).replaceAll("[controller]", m.getDeclaringType().getName().regexpReplaceAll("Controller$", ""))
  )
  or
  not exists(Attribute ca | ca = m.getDeclaringType().getAnAttribute() and httpMethodAttr(ca, _)) and
  result = ""
}

/** Attribute-routed MVC/API controller actions. */
predicate attrEndpoint(Method m, string verb, string route, string handlerRef) {
  exists(Attribute a, string rawRoute |
    a = m.getAnAttribute() and
    httpMethodAttr(a, verb) and
    rawRoute = attrRoute(a) and
    (if classPrefix(m) = ""
     then route = rawRoute
     else route = "/" + classPrefix(m).regexpReplaceAll("^/|/$", "") + "/" + rawRoute.regexpReplaceAll("^/", "")) and
    route != "" and
    handlerRef = m.getName() + "@" + m.getFile().getRelativePath() + ":" +
        m.getLocation().getStartLine().toString()
  )
}

/** Minimal-API route registration: app.MapGet("/path", handler) etc. */
predicate minimalApiCall(MethodCall call, string verb) {
  exists(string n | n = call.getTarget().getName() |
    n = "MapGet" and verb = "GET"
    or
    n = "MapPost" and verb = "POST"
    or
    n = "MapPut" and verb = "PUT"
    or
    n = "MapDelete" and verb = "DELETE"
    or
    n = "MapPatch" and verb = "PATCH"
    or
    n = "Map" and verb = ""
  ) and
  call.getTarget().getDeclaringType().getNamespace().getFullName().matches("Microsoft.AspNetCore%")
}

/**
 * `app.MapGet(route, handler)` is an extension method on IEndpointRouteBuilder:
 * called with instance syntax, CodeQL numbers the implicit receiver (`app`) as
 * argument 0, so the route is argument 1 and the handler argument 2.
 */
string minimalApiRoute(MethodCall call) {
  exists(Expr e | e = call.getArgument(1) | result = e.getValue())
}

/** The handler: a lambda/anonymous method, or a named method-group reference. */
string minimalApiHandlerRef(MethodCall call) {
  exists(AnonymousFunctionExpr f | f = call.getArgument(2) |
    result = "anonymous@" + f.getFile().getRelativePath() + ":" + f.getLocation().getStartLine().toString()
  )
  or
  not call.getArgument(2) instanceof AnonymousFunctionExpr and
  result = "handler@" + call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString()
}

predicate minimalApiEndpoint(MethodCall call, string verb, string route, string handlerRef) {
  minimalApiCall(call, verb) and
  route = minimalApiRoute(call) and
  route.matches("/%") and
  handlerRef = minimalApiHandlerRef(call)
}

from Element e, string verb, string route, string handlerRef
where
  attrEndpoint(e, verb, route, handlerRef)
  or
  minimalApiEndpoint(e, verb, route, handlerRef)
select e, "ENDPOINT|http|" + verb + "|" + route + "|" + handlerRef
