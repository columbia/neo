/**
 * @name JavaScript Function Definitions
 * @description Extract named function/method definitions with metadata.
 * @kind problem
 * @problem.severity info
 * @id javascript/function-definitions
 * @tags function-extraction
 */

import javascript

/** Name of a function: explicit/inferred where CodeQL has one, else a stable
 *  synthetic name so anonymous callbacks (Express `app.post('/x', (req,res)=>…)`)
 *  still get a call-graph node. */
string fnName(Function f) {
  if f.getName() != "" then result = f.getName() else result = "anonymous"
}

/** Declaring class name for a method body, "" for free functions. */
string className(Function f) {
  exists(MethodDeclaration m | m.getBody() = f | result = m.getDeclaringClass().getName())
  or
  not exists(MethodDeclaration m | m.getBody() = f) and result = ""
}

string params(Function f) {
  result = concat(string p, int i |
      p = f.getParameter(i).(SimpleParameter).getName()
    |
      p, ", " order by i
    )
}

bindingset[relpath]
string dirOf(string relpath) { result = relpath.regexpReplaceAll("/[^/]+$", "") }

from Function f, string name, string rel
where
  name = fnName(f) and
  // keep every named function; for anonymous ones require a real `{ … }` body
  // so trivial expression lambdas (`x => x.id`) don't flood the call graph
  (f.getName() != "" or f.getBody() instanceof BlockStmt) and
  rel = f.getFile().getRelativePath() and
  rel.regexpMatch("(?i).*\\.(js|mjs|cjs|jsx|ts|tsx)$") and
  not rel.matches("%/node_modules/%") and
  not rel.matches("%/dist/%") and
  not rel.matches("%/build/%") and
  not rel.matches("%.min.js")
select f,
  // function_id|name|file|start|end|signature|class|package|annotations
  name + "@" + rel + ":" + f.getLocation().getStartLine().toString() +
  "|" + name +
  "|" + rel +
  "|" + f.getLocation().getStartLine().toString() +
  "|" + f.getLocation().getEndLine().toString() +
  "|" + "function " + name + "(" + params(f) + ")" +
  "|" + className(f) +
  "|" + dirOf(rel) +
  "|"
