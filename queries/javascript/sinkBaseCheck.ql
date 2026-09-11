/**
 * @name JavaScript Authentication & Authorization Discovery
 * @description Discovers high-confidence authentication and authorization checks
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id javascript/auth-discovery
 * @tags security authentication authorization
 */

import javascript

// Auth method detection - focus on actual security checks
predicate isAuthMethod(Function func) {
  func.getName().regexpMatch(".*(?i)(authenticate|isAuthenticated|checkAuth|verifyAuth|login|logout|hasRole|hasPermission|isAuthorized|checkPermission|checkRole|canAccess|isAdmin|isOwner|validateUser|verifyUser|checkAccess|hasAccess|isAllowed|checkCredentials|verifyCredentials|hasAuthority).*") and
  // Exclude common false positives
  not func.getName().regexpMatch(".*(?i)(test|mock|stub|example|demo|sample).*")
}

// Auth variables - focus on security context
predicate isAuthVariable(Variable var) {
  var.getName().regexpMatch(".*(?i)(authenticated|authorized|currentUser|principal|subject|securityContext|userRole|userPermission|isAdmin|isOwner|hasAccess|canAccess|allowAccess|grantAccess).*")
}

// Check if the if statement is likely a security gate
predicate isSecurityGate(IfStmt ifstmt) {
  exists(ifstmt.getThen()) and
  (
    // Throws security exception
    exists(ThrowStmt throw | throw.getContainer() = ifstmt.getThen()) or
    // Returns early (common auth pattern)
    exists(ReturnStmt ret | ret.getContainer() = ifstmt.getThen()) or
    // Redirects or sends error
    exists(Expr call |
      call.getContainer() = ifstmt.getThen() and
      call.toString().regexpMatch(".*(?i)(redirect|sendStatus|status|send|json|render).*")
    ) or
    // Has else branch (decision point)
    exists(ifstmt.getElse())
  )
}

from IfStmt ifstmt, Function containingFunc, string patternType, string expression
where
  // Must be a security gate
  isSecurityGate(ifstmt) and

  // Get the containing function
  containingFunc = ifstmt.getContainer() and

  (
    // Direct auth method calls in condition
    exists(InvokeExpr call |
      ifstmt.getCondition().getAChildExpr*() = call and
      isAuthMethod(call.getResolvedCallee()) and
      patternType = "auth_method_call" and
      expression = ifstmt.getCondition().toString()
    )
    or
    // High-confidence auth variables
    exists(VarAccess var |
      ifstmt.getCondition().getAChildExpr*() = var and
      isAuthVariable(var.getVariable()) and
      patternType = "auth_variable_check" and
      expression = ifstmt.getCondition().toString()
    )
    or
    // Property access for auth checks
    exists(PropAccess prop |
      ifstmt.getCondition().getAChildExpr*() = prop and
      prop.getPropertyName().regexpMatch(".*(?i)(authenticated|authorized|isAdmin|isOwner|hasAccess|canAccess|role|permission).*") and
      patternType = "auth_property_check" and
      expression = ifstmt.getCondition().toString()
    )
  )

select ifstmt,
       expression + " OCCURRED IN FUNCTION " + containingFunc.getName() + " AT " +
       containingFunc.getFile().getRelativePath() + ":" +
       containingFunc.getStartLine().toString()
