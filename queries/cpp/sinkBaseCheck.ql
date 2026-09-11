/**
 * @name C++ Authentication & Authorization Discovery
 * @description Discovers authentication and authorization checks in C++ code
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id cpp/auth-discovery
 * @tags security authentication authorization
 */

import cpp

predicate isAuthFunction(Function f) {
  (f.getName().toLowerCase().matches("%authenticate%") or
  f.getName().toLowerCase().matches("%authorize%") or
  f.getName().toLowerCase().matches("%checkauth%") or
  f.getName().toLowerCase().matches("%verifyauth%") or
  f.getName().toLowerCase().matches("%checkpermission%") or
  f.getName().toLowerCase().matches("%haspermission%") or
  f.getName().toLowerCase().matches("%isadmin%") or
  f.getName().toLowerCase().matches("%isowner%") or
  f.getName().toLowerCase().matches("%checkaccess%") or
  f.getName().toLowerCase().matches("%validateuser%") or
  f.getName().toLowerCase().matches("%verifytoken%") or
  f.getName().toLowerCase().matches("%verifyjwt%")) and
  not (f.getName().toLowerCase().matches("%test%") or
  f.getName().toLowerCase().matches("%mock%") or
  f.getName().toLowerCase().matches("%stub%"))
}

predicate isAuthVariable(LocalVariable v) {
  v.getName().toLowerCase().matches("%authenticated%") or
  v.getName().toLowerCase().matches("%authorized%") or
  v.getName().toLowerCase().matches("%isadmin%") or
  v.getName().toLowerCase().matches("%hasaccess%") or
  v.getName().toLowerCase().matches("%permission%") or
  v.getName().toLowerCase().matches("%role%") or
  v.getName().toLowerCase().matches("%token%")
}

predicate isSecurityGate(IfStmt s) {
  exists(s.getThen()) and
  (exists(ReturnStmt r | r.getParent+() = s.getThen()) or
   exists(s.getElse()) or
   exists(ThrowExpr t | t.getParent+() = s.getThen()))
}

from IfStmt ifstmt, Function containingFunction, string patternType, string expression, string callTarget
where
  isSecurityGate(ifstmt) and
  containingFunction = ifstmt.getEnclosingFunction() and
  (
    exists(FunctionCall call, Function f |
      call = ifstmt.getCondition().getAChild*() and
      f = call.getTarget() and
      isAuthFunction(f) and
      patternType = "auth_function_call" and
      expression = ifstmt.getCondition().toString() and
      callTarget = f.getName()
    ) or
    exists(VariableAccess va, LocalVariable v |
      va = ifstmt.getCondition().getAChild*() and
      v = va.getTarget() and
      isAuthVariable(v) and
      patternType = "auth_variable_check" and
      expression = ifstmt.getCondition().toString() and
      callTarget = v.getName()
    )
  )
select ifstmt,
  expression + " OCCURRED IN FUNCTION " + containingFunction.getName() + " AT " +
  containingFunction.getFile().getRelativePath() + ":" +
  containingFunction.getLocation().getStartLine().toString() + ":" +
  containingFunction.getLocation().getEndLine().toString()
