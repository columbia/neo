/**
 * @name Qast: locate AST constructs of a given kind
 * @description {{OP}} is filled by src/genquery/gen_astsearch.py with one of:
 *              call | method | field_access | assignment | return | string_literal |
 *              conditional | catch | parameter | new
 * @kind problem
 * @problem.severity info
 * @id neo/qast
 */

import javascript

predicate isOp(Locatable e, string op) {
  op = "call" and e instanceof CallExpr
  or
  op = "new" and e instanceof NewExpr
  or
  op = "method" and e instanceof Function
  or
  op = "field_access" and e instanceof PropAccess
  or
  op = "assignment" and e instanceof AssignExpr
  or
  op = "return" and e instanceof ReturnStmt
  or
  op = "string_literal" and e instanceof StringLiteral
  or
  op = "conditional" and (e instanceof IfStmt or e instanceof ConditionalExpr or e instanceof SwitchStmt)
  or
  op = "catch" and e instanceof CatchClause
  or
  op = "parameter" and e instanceof Parameter
}

string label(Locatable e) {
  e.(Function).getName() != "" and result = e.(Function).getName()
  or
  not (e instanceof Function and e.(Function).getName() != "") and
  result = e.toString().replaceAll("\n", " ")
}

from Locatable e, string rel
where
  isOp(e, "{{OP}}") and
  rel = e.getFile().getRelativePath() and
  rel.regexpMatch("(?i).*\\.(js|mjs|cjs|jsx|ts|tsx)$") and
  not rel.matches("%/node_modules/%") and
  not rel.matches("%.min.js")
select e, "AST|{{OP}}|" + label(e) + "|" + rel + ":" + e.getLocation().getStartLine().toString()
