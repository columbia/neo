/**
 * @name Inbound HTTP endpoints and handlers
 * @description Lists inbound HTTP routes (FastAPI / Flask / Django-style
 *              decorators) together with their handler function.
 * @kind problem
 * @problem.severity info
 * @id neo/endpoints-in
 */

import python

/**
 * A route decorator `@x.<verb>("<route>")` on `func`.
 * Handles FastAPI/Flask style: `@app.get(...)`, `@router.post(...)`,
 * `@app.route(...)` (verb unknown -> "").
 */
predicate routeDecorator(Function func, Call deco, string verb, string route) {
  deco = func.getADecorator() and
  exists(Attribute attr | attr = deco.getFunc() |
    exists(string m | m = attr.getName() |
      (
        m in ["get", "post", "put", "delete", "patch", "head", "options"] and
        verb = m.toUpperCase()
        or
        m = "route" and verb = ""
      )
    )
  ) and
  exists(StrConst s | s = deco.getArg(0) and route = s.getText())
}

from Function func, Call deco, string verb, string route
where routeDecorator(func, deco, verb, route)
select func,
  "ENDPOINT|http|" + verb + "|" + route + "|" + func.getName() + "@" +
    func.getLocation().getFile().getRelativePath() + ":" +
    func.getLocation().getStartLine().toString()
