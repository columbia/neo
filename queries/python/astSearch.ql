/**
 * @name Qast: locate AST constructs of a given kind
 * @description {{OP}} is filled by src/genquery/gen_astsearch.py with one of:
 *              call | method | field_access | assignment | return | string_literal |
 *              conditional | catch | parameter
 * @kind problem
 * @problem.severity info
 * @id neo/qast
 */

import python

predicate isOp(AstNode e, string op) {
  op = "call" and e instanceof Call
  or
  op = "method" and e instanceof Function
  or
  op = "field_access" and e instanceof Attribute
  or
  op = "assignment" and e instanceof Assign
  or
  op = "return" and e instanceof Return
  or
  op = "string_literal" and e instanceof StrConst
  or
  op = "conditional" and (e instanceof If or e instanceof IfExp)
  or
  op = "catch" and e instanceof ExceptStmt
  or
  op = "parameter" and e instanceof Parameter
}

string label(AstNode e) {
  result = e.(Function).getName()
  or
  not e instanceof Function and result = e.toString().replaceAll("\n", " ")
}

from AstNode e
where
  isOp(e, "{{OP}}") and
  exists(e.getLocation().getFile().getRelativePath()) and
  not e.getLocation().getFile().getRelativePath().matches(["%/test/%", "%/site-packages/%"])
select e,
  "AST|{{OP}}|" + label(e) + "|" + e.getLocation().getFile().getRelativePath() + ":" +
    e.getLocation().getStartLine().toString()
