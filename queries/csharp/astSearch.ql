/**
 * @name Qast: locate AST constructs of a given kind
 * @description {{OP}} is filled by src/genquery/gen_astsearch.py with one of:
 *              call | method | field_access | assignment | return | string_literal |
 *              conditional | catch | parameter | new
 * @kind problem
 * @problem.severity info
 * @id neo/qast
 */

import csharp

predicate isOp(Element e, string op) {
  op = "call" and e instanceof MethodCall
  or
  op = "new" and e instanceof ObjectCreation
  or
  op = "method" and e instanceof Callable
  or
  op = "field_access" and e instanceof FieldAccess
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

string label(Element e) {
  result = e.(Callable).getName()
  or
  not e instanceof Callable and result = e.toString().replaceAll("\n", " ")
}

from Element e
where
  isOp(e, "{{OP}}") and
  exists(e.getLocation().getFile().getRelativePath()) and
  e.getLocation().getFile().getRelativePath().matches("%.cs") and
  not e.getLocation().getFile().getRelativePath().matches(["%/obj/%", "%/bin/%"])
select e,
  "AST|{{OP}}|" + label(e) + "|" + e.getLocation().getFile().getRelativePath() + ":" +
    e.getLocation().getStartLine().toString()
