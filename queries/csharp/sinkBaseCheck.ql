/**
 * @name C# Authentication & Authorization Discovery
 * @description Discovers high-confidence authentication and authorization checks
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id csharp/neo
 * @tags security authentication authorization
 */

import csharp

// Auth method detection
predicate isAuthMethod(Callable method) {
  method.getName()
      .regexpMatch(".*(?i)(Authenticate|IsAuthenticated|CheckAuth|VerifyAuth|Login|Logout|HasRole|HasPermission|IsAuthorized|CheckPermission|CheckRole|CanAccess|IsAdmin|IsOwner|ValidateUser|VerifyUser|CheckAccess|HasAccess|IsAllowed|CheckCredentials|VerifyCredentials|HasAuthority|RequireRole|RequirePermission).*") and
  not method.getName().regexpMatch(".*(?i)(test|mock|stub|example|demo|sample).*")
}

// Security framework types
predicate isSecurityFrameworkType(ValueOrRefType t) {
  t.getFullyQualifiedName().matches("Microsoft.AspNetCore.Authorization.%")
  or
  t.getFullyQualifiedName().matches("Microsoft.AspNetCore.Identity.%")
  or
  t.getFullyQualifiedName().matches("System.Security.Claims.%")
  or
  t.getFullyQualifiedName().matches("System.Security.Principal.%")
}

// Auth variables
predicate isAuthVariable(Variable var) {
  var.getName()
      .regexpMatch(".*(?i)(authenticated|authorized|currentUser|principal|subject|securityContext|userRole|userPermission|isAdmin|isOwner|hasAccess|canAccess|allowAccess|grantAccess).*") and
  (
    var.getType().getName() in ["bool", "Boolean"] or
    isSecurityFrameworkType(var.getType())
  )
}

// Auth properties
predicate isAuthProperty(Property prop) {
  prop.getName()
      .regexpMatch(".*(?i)(IsAuthenticated|IsAuthorized|IsAdmin|IsOwner|HasAccess|CanAccess|IsActive|IsEnabled|HasRole|HasPermission).*") and
  (
    prop.getType().getName() in ["bool", "Boolean"] or
    isSecurityFrameworkType(prop.getType())
  )
}

// If statement is a security gate
predicate isSecurityGate(IfStmt ifstmt) {
  (
    ifstmt.getThen().getAChildStmt*() instanceof ThrowStmt
    or
    ifstmt.getThen().getAChildStmt*() instanceof ReturnStmt
    or
    exists(MethodCall mc |
      ifstmt.getThen().getAChildStmt*() = mc.getEnclosingStmt() and
      mc.getTarget().getName().regexpMatch(".*(?i)(Redirect|Forbid|Unauthorized|Challenge|SignOut|AccessDenied).*")
    )
    or
    exists(ifstmt.getElse())
  )
}

from IfStmt ifstmt, Callable containingMethod, string pattern_type, string expression, string call_target
where
  isSecurityGate(ifstmt) and
  containingMethod = ifstmt.getEnclosingCallable() and
  exists(containingMethod.getBody()) and
  (
    // Direct auth method calls in condition
    exists(MethodCall mc |
      ifstmt.getCondition().getAChildExpr*() = mc and
      isAuthMethod(mc.getTarget()) and
      pattern_type = "auth_method_call" and
      expression = ifstmt.getCondition().toString() and
      call_target = mc.getTarget().getDeclaringType().getName() + "." + mc.getTarget().getName()
    )
    or
    // Security framework calls
    exists(MethodCall mc |
      ifstmt.getCondition().getAChildExpr*() = mc and
      isSecurityFrameworkType(mc.getTarget().getDeclaringType()) and
      pattern_type = "framework_security_call" and
      expression = ifstmt.getCondition().toString() and
      call_target = mc.getTarget().getDeclaringType().getName() + "." + mc.getTarget().getName()
    )
    or
    // Auth variable checks
    exists(LocalVariableRead vr |
      ifstmt.getCondition().getAChildExpr*() = vr and
      isAuthVariable(vr.getTarget()) and
      pattern_type = "auth_variable_check" and
      expression = ifstmt.getCondition().toString() and
      call_target = vr.getTarget().getName()
    )
    or
    // Auth property access
    exists(PropertyAccess pa |
      ifstmt.getCondition().getAChildExpr*() = pa and
      isAuthProperty(pa.getTarget()) and
      pattern_type = "auth_property_check" and
      expression = ifstmt.getCondition().toString() and
      call_target = pa.getTarget().getName()
    )
    or
    // [Authorize] attribute on containing method
    exists(Attribute attr |
      attr = containingMethod.(Method).getAnAttribute() and
      attr.getType().getName().matches("%Authorize%") and
      pattern_type = "authorize_attribute" and
      expression = attr.toString() and
      call_target = attr.getType().getName()
    )
  )

select ifstmt,
  expression + " OCCURRED IN FUNCTION " + containingMethod.getName() + " AT " +
  containingMethod.getLocation().getFile().getRelativePath() + ":" +
  containingMethod.getLocation().getStartLine().toString() + ":" +
  containingMethod.getLocation().getEndLine().toString()
