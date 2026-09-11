/**
 * @name Java Authentication & Authorization Discovery - Refined
 * @description Discovers high-confidence authentication and authorization checks
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id neo
 * @tags security authentication authorization
 */

import java

// More precise auth method detection - focus on actual security checks
predicate isAuthMethod(Method method) {
  method.getName().regexpMatch(".*(?i)(authenticate|isAuthenticated|checkAuth|verifyAuth|login|logout|hasRole|hasPermission|isAuthorized|checkPermission|checkRole|canAccess|isAdmin|isOwner|validateUser|verifyUser|checkAccess|hasAccess|isAllowed|checkCredentials|verifyCredentials|hasAuthority).*") and
  // Exclude common false positives
  not method.getName().regexpMatch(".*(?i)(test|mock|stub|example|demo|sample).*")
}

// Focus on well-known security frameworks
predicate isSecurityFramework(RefType type) {
  type.getQualifiedName().matches([
    "org.springframework.security.%",
    "javax.security.%", 
    "jakarta.security.%",
    "org.apache.shiro.%",
    "com.auth0.%"
  ])
}

// More specific auth variables - focus on security context
predicate isAuthVariable(Variable var) {
  var.getName().regexpMatch(".*(?i)(authenticated|authorized|currentUser|principal|subject|securityContext|userRole|userPermission|isAdmin|isOwner|hasAccess|canAccess|allowAccess|grantAccess).*") and
  // Must be boolean or security-related type
  (
    var.getType().hasName(["boolean", "Boolean"]) or
    isSecurityFramework(var.getType()) or
    var.getType().getName().regexpMatch(".*(?i)(User|Principal|Subject|Role|Permission|Authority|Security|Auth).*")
  )
}

// High-confidence auth fields
predicate isAuthField(Field field) {
  field.getName().regexpMatch(".*(?i)(authenticated|authorized|isAdmin|isOwner|hasAccess|canAccess|allowAccess|grantAccess|isActive|isEnabled|isValid|hasRole|hasPermission).*") and
  (
    field.getType().hasName(["boolean", "Boolean"]) or
    isSecurityFramework(field.getType()) or
    field.getType().getName().regexpMatch(".*(?i)(User|Principal|Subject|Role|Permission|Authority|Security|Auth).*")
  )
}

// Check if the if statement is likely a security gate
predicate isSecurityGate(IfStmt ifstmt) {
  // Must have a then branch that does something meaningful
  exists(ifstmt.getThen()) and
  (
    // Throws security exception
    exists(ThrowStmt throw | throw.getEnclosingStmt().getParent*() = ifstmt.getThen()) or
    // Returns early (common auth pattern)
    exists(ReturnStmt ret | ret.getEnclosingStmt().getParent*() = ifstmt.getThen()) or
    // Redirects or forwards (web auth pattern)
    exists(Call call | 
      call.getEnclosingStmt().getParent*() = ifstmt.getThen() and
      call.getCallee().getName().regexpMatch(".*(?i)(redirect|forward|sendError|setStatus).*")
    ) or
    // Has else branch (decision point)
    exists(ifstmt.getElse())
  )
}

from IfStmt ifstmt, Method containingMethod, string pattern_type, string expression, string call_target
where
  // Must be a security gate
  isSecurityGate(ifstmt) and
  
  // Get the containing method
  containingMethod = ifstmt.getEnclosingCallable() and
  exists(containingMethod.getBody()) and
  
  (
    // Direct auth method calls in condition
    exists(Call call, Method method |
      ifstmt.getCondition().getAChildExpr*() = call and
      method = call.getCallee() and
      isAuthMethod(method) and
      pattern_type = "auth_method_call" and
      expression = ifstmt.getCondition().toString() and
      call_target = method.getDeclaringType().getName() + "." + method.getName()
    )
    or
    // Security framework calls
    exists(Call call, Method method |
      ifstmt.getCondition().getAChildExpr*() = call and
      method = call.getCallee() and
      isSecurityFramework(method.getDeclaringType()) and
      pattern_type = "framework_security_call" and
      expression = ifstmt.getCondition().toString() and
      call_target = method.getDeclaringType().getName() + "." + method.getName()
    )
    or
    // High-confidence auth variables
    exists(VarAccess var |
      ifstmt.getCondition().getAChildExpr*() = var and
      isAuthVariable(var.getVariable()) and
      pattern_type = "auth_variable_check" and
      expression = ifstmt.getCondition().toString() and
      call_target = var.getVariable().getName()
    )
    or
    // High-confidence auth fields
    exists(FieldAccess field |
      ifstmt.getCondition().getAChildExpr*() = field and
      isAuthField(field.getField()) and
      pattern_type = "auth_field_check" and
      expression = ifstmt.getCondition().toString() and
      call_target = field.getField().getName()
    )
  )

select ifstmt,
       expression + " OCCURRED IN FUNCTION " + containingMethod.getName() +  " AT " + containingMethod.getFile().getRelativePath() + ":" + containingMethod.getLocation().getStartLine().toString() + ":" + (containingMethod.getLocation().getStartLine() + containingMethod.getLocation().getNumberOfLines() - 1).toString()
       