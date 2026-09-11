/**
 * @name Inbound HTTP endpoints and handlers
 * @description Lists inbound HTTP routes (Spring MVC / JAX-RS style) together
 *              with their handler method, for cross-service flow stitching.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import java

/** A Spring / JAX-RS mapping annotation and the HTTP verb it implies. */
predicate mappingAnnotation(Annotation a, string verb) {
  exists(string n | n = a.getType().getName() |
    n = "GetMapping" and verb = "GET"
    or
    n = "PostMapping" and verb = "POST"
    or
    n = "PutMapping" and verb = "PUT"
    or
    n = "DeleteMapping" and verb = "DELETE"
    or
    n = "PatchMapping" and verb = "PATCH"
    or
    n = "RequestMapping" and verb = ""
    or
    n = "GET" and verb = "GET"
    or
    n = "POST" and verb = "POST"
    or
    n = "PUT" and verb = "PUT"
    or
    n = "DELETE" and verb = "DELETE"
    or
    n = "Path" and verb = ""
  )
}

/** The literal string value(s) of an annotation's `value` / `path` element. */
string annotationPath(Annotation a) {
  result = a.getValue("value").(CompileTimeConstantExpr).getStringValue()
  or
  result = a.getValue("path").(CompileTimeConstantExpr).getStringValue()
  or
  result = a.getAnArrayValue("value").(CompileTimeConstantExpr).getStringValue()
  or
  result = a.getAnArrayValue("path").(CompileTimeConstantExpr).getStringValue()
  or
  not exists(a.getValue("value")) and
  not exists(a.getValue("path")) and
  not exists(a.getAnArrayValue("value")) and
  result = ""
}

/** Route prefix from a class-level mapping annotation, "" if none. */
string classPrefix(Method m) {
  exists(Annotation ca |
    ca = m.getDeclaringType().getAnAnnotation() and
    mappingAnnotation(ca, _) and
    result = annotationPath(ca)
  )
  or
  not exists(Annotation ca |
    ca = m.getDeclaringType().getAnAnnotation() and mappingAnnotation(ca, _)
  ) and
  result = ""
}

bindingset[a, b]
string joinSeg(string a, string b) {
  if a = "" then result = b
  else
    if b = "" then result = a
    else result = a + "/" + b
}

from Method m, Annotation a, string verb, string route, string full
where
  a = m.getAnAnnotation() and
  mappingAnnotation(a, verb) and
  route = annotationPath(a) and
  full = joinSeg(classPrefix(m).regexpReplaceAll("/$", ""), route.regexpReplaceAll("^/", ""))
select m,
  "ENDPOINT|http|" + verb + "|/" + full.regexpReplaceAll("^/", "") + "|" + m.getName() + "@" +
    m.getLocation().getFile().getRelativePath() + ":" + m.getLocation().getStartLine().toString()
