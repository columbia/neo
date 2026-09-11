/**
 * @name Python Authentication & Authorization Discovery - Refined
 * @description Discovers high-confidence authentication and authorization checks
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id python/neo
 * @tags security authentication authorization
 */

import python

// More precise auth method detection - focus on actual security checks
predicate isAuthMethod(Function method) {
  method.getName().regexpMatch(".*(?i)(authenticate|is_authenticated|check_auth|verify_auth|login|logout|has_role|has_permission|is_authorized|check_permission|check_role|can_access|is_admin|is_owner|validate_user|verify_user|check_access|has_access|is_allowed|check_credentials|verify_credentials|has_authority).*") and
  // Exclude common false positives
  not method.getName().regexpMatch(".*(?i)(test|mock|stub|example|demo|sample).*")
}

// Focus on well-known security frameworks by module name
predicate isSecurityFrameworkModule(Module mod) {
  mod.getName().matches([
    "django.contrib.auth.%",
    "flask_login.%", 
    "flask_security.%",
    "authlib.%",
    "jwt.%",
    "cryptography.%",
    "passlib.%",
    "oauth2lib.%"
  ])
}

// More specific auth variables - focus on security context
predicate isAuthVariable(Variable var) {
  var.getId().regexpMatch(".*(?i)(authenticated|authorized|current_user|principal|subject|security_context|user_role|user_permission|is_admin|is_owner|has_access|can_access|allow_access|grant_access).*")
}

// High-confidence auth attributes
predicate isAuthAttribute(Attribute attr) {
  attr.getName().regexpMatch(".*(?i)(authenticated|authorized|is_admin|is_owner|has_access|can_access|allow_access|grant_access|is_active|is_enabled|is_valid|has_role|has_permission).*")
}

// Check if the if statement is likely a security gate
predicate isSecurityGate(If ifstmt) {
  // Must have a then branch that does something meaningful
  exists(ifstmt.getBody()) and
  (
    // Raises security exception
    exists(Raise raise | raise.getScope() = ifstmt.getScope()) or
    // Returns early (common auth pattern)  
    exists(Return ret | ret.getScope() = ifstmt.getScope()) or
    // Has else branch (decision point)
    exists(ifstmt.getOrelse())
  )
}

from If ifstmt, Function containingMethod, string pattern_type, string expression, string call_target
where
  // Must be a security gate
  isSecurityGate(ifstmt) and
  
  // Get the containing method
  containingMethod = ifstmt.getScope() and
  
  (
    // Direct auth method calls in condition
    exists(Call call, Value val, Function method |
      call.getASubExpression*() = ifstmt.getTest().getASubExpression*() and
      call.getFunc().pointsTo(val) and
      val.(CallableValue).getScope() = method and
      isAuthMethod(method) and
      pattern_type = "auth_method_call" and
      expression = ifstmt.getTest().toString() and
      call_target = method.getName()
    )
    or
    // Security framework calls
    exists(Call call, Value val, Function method, Module mod |
      call.getASubExpression*() = ifstmt.getTest().getASubExpression*() and
      call.getFunc().pointsTo(val) and
      val.(CallableValue).getScope() = method and
      mod = method.getScope() and
      isSecurityFrameworkModule(mod) and
      pattern_type = "framework_security_call" and
      expression = ifstmt.getTest().toString() and
      call_target = method.getName()
    )
    or
    // High-confidence auth variables
    exists(Name var |
      var.getASubExpression*() = ifstmt.getTest().getASubExpression*() and
      isAuthVariable(var.getVariable()) and
      pattern_type = "auth_variable_check" and
      expression = ifstmt.getTest().toString() and
      call_target = var.getId()
    )
    or
    // High-confidence auth attributes
    exists(Attribute attr |
      attr.getASubExpression*() = ifstmt.getTest().getASubExpression*() and
      isAuthAttribute(attr) and
      pattern_type = "auth_attribute_check" and
      expression = ifstmt.getTest().toString() and
      call_target = attr.getName()
    )
  )

select ifstmt,
       expression + " OCCURRED IN FUNCTION " + containingMethod.getName() +  " AT " 
       + containingMethod.getLocation().getFile().getRelativePath() + ":" + containingMethod.getLocation().getStartLine().toString() + ":"
       + containingMethod.getLocation().getEndLine().toString()