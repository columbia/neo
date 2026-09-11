/**
 * @name Qast: locate AST constructs of a given kind
 * @description {{OP}} is filled by src/genquery/gen_astsearch.py with one of:
 *              call | method | field_access | assignment | return | string_literal |
 *              conditional | parameter
 * @kind problem
 * @problem.severity info
 * @id neo/qast
 */

import go

predicate isOp(AstNode e, string op) {
  op = "call" and e instanceof CallExpr
  or
  op = "method" and e instanceof FuncDecl
  or
  op = "field_access" and e instanceof SelectorExpr
  or
  op = "assignment" and e instanceof AssignStmt
  or
  op = "return" and e instanceof ReturnStmt
  or
  op = "string_literal" and e instanceof StringLit
  or
  op = "conditional" and (e instanceof IfStmt or e instanceof SwitchStmt)
  or
  op = "parameter" and e instanceof FuncTypeExpr
}

string label(AstNode e) {
  result = e.(FuncDecl).getName()
  or
  not e instanceof FuncDecl and result = e.toString().replaceAll("\n", " ")
}

from AstNode e
where
  isOp(e, "{{OP}}") and
  e.getFile().getRelativePath().matches("%.go") and
  not e.getFile().getRelativePath().matches("%/vendor/%")
select e,
  "AST|{{OP}}|" + label(e) + "|" + e.getFile().getRelativePath() + ":" +
    e.getLocation().getStartLine().toString()
