/**
 * @name Go Authentication & Authorization Discovery
 * @description Discovers high-confidence authentication and authorization checks
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id go/auth-discovery
 * @tags security authentication authorization
 */

import go

// Auth method detection - focus on actual security checks
predicate isAuthMethod(Function f) {
  f.getName().regexpMatch("(?i).*(authenticate|is_authenticated|check_auth|verify_auth|login|logout|has_role|has_permission|is_authorized|check_permission|check_role|can_access|is_admin|is_owner|validate_user|verify_user|check_access|has_access|is_allowed|check_credentials|verify_credentials|has_authority).*") and
  // Exclude test functions
  not f.getName().regexpMatch("(?i).*(test|mock|stub|example|demo|sample).*")
}

// Security framework detection
predicate isSecurityFrameworkType(Type t) {
  t.getPackage().getPath().matches([
    "github.com/gin-gonic/gin%",
    "github.com/casbin/casbin%",
    "github.com/golang-jwt/jwt%",
    "golang.org/x/oauth2%"
  ])
}

// Auth variables
predicate isAuthVariable(Variable var) {
  var.getName().regexpMatch("(?i).*(authenticated|authorized|current_user|principal|subject|security_context|user_role|user_permission|is_admin|is_owner|has_access|can_access|allow_access|grant_access).*")
}

// Check if the if statement is likely a security gate
predicate isSecurityGate(IfStmt ifstmt) {
  exists(ifstmt.getThen()) and
  (
    // Returns early (common auth pattern)
    exists(ReturnStmt ret | ret.getParent*() = ifstmt.getThen()) or
    // Has else branch (decision point)
    exists(ifstmt.getElse())
  )
}

from IfStmt ifstmt, FuncDef containingFunction, string pattern_type, string expression, string call_target
where
  // Must be a security gate
  isSecurityGate(ifstmt) and

  // Get the containing function
  containingFunction = ifstmt.getEnclosingFunction() and
  
  (
    // Direct auth method calls in condition
    exists(DataFlow::CallNode call, Function f |
      call.asExpr() = ifstmt.getCond().getAChild*() and
      f = call.getTarget() and
      isAuthMethod(f) and
      pattern_type = "auth_method_call" and
      expression = ifstmt.getCond().toString() and
      call_target = f.getName()
    )
    or
    // Security framework calls (methods only)
    exists(DataFlow::MethodCallNode call, Method m |
      call.asExpr() = ifstmt.getCond().getAChild*() and
      m = call.getTarget() and
      isSecurityFrameworkType(m.getReceiverType()) and
      pattern_type = "framework_security_call" and
      expression = ifstmt.getCond().toString() and
      call_target = m.getName()
    )
    or
    // High-confidence auth variables
    exists(Ident id, Variable var |
      id = ifstmt.getCond().getAChild*() and
      id.uses(var) and
      isAuthVariable(var) and
      pattern_type = "auth_variable_check" and
      expression = ifstmt.getCond().toString() and
      call_target = id.toString()
    )
  )

select ifstmt,
  expression + " OCCURRED IN FUNCTION " + containingFunction.getName() + " AT " +
  containingFunction.(FuncDecl).getFile().getRelativePath() + ":" +
  containingFunction.getLocation().getStartLine().toString() + ":" +
  containingFunction.getLocation().getEndLine().toString()