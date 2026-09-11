import cpp
import semmle.code.cpp.dataflow.new.DataFlow

/**
 * Additional taint steps the stock C++ taint-tracking library doesn't always
 * carry, needed because privileged sinks routinely receive a `std::string`
 * built from tainted input: ``a + b`` / ``a += b`` on std::string,
 * ``.c_str()`` / ``.data()``, an ``std::string`` constructor, and the
 * printf/strcat family.
 */
predicate stringStep(DataFlow::Node n1, DataFlow::Node n2) {
  exists(Call c |
    c.getTarget().getName() in [
      "operator+", "operator+=", "append", "assign", "insert", "replace",
      "c_str", "data", "basic_string", "string"
    ] and
    (c.getAnArgument() = n1.asExpr() or c.getQualifier() = n1.asExpr()) and
    (n2.asExpr() = c or c.getQualifier() = n2.asExpr())
  )
  or
  exists(FunctionCall fc |
    fc.getTarget().getName().regexpMatch("s?n?printf|v?s?n?printf|strn?cat|strn?cpy|memcpy|stpcpy") and
    fc.getAnArgument() = n1.asExpr() and
    fc.getArgument(0) = n2.asExpr()
  )
}

/**
 * Flow-insensitive assignment step: whatever initialises or is assigned to a
 * local variable reaches every read of that variable. Coarse, but bounded by
 * the config's own source/sink scoping.
 */
predicate assignStep(DataFlow::Node n1, DataFlow::Node n2) {
  exists(LocalScopeVariable v |
    n1.asExpr() = v.getInitializer().getExpr() and
    n2.asExpr() = v.getAnAccess()
  )
  or
  exists(AssignExpr a, LocalScopeVariable v |
    a.getLValue() = v.getAnAccess() and
    n1.asExpr() = a.getRValue() and
    n2.asExpr() = v.getAnAccess()
  )
}

/** Both steps together -- the usual choice for `isAdditionalFlowStep`. */
predicate cppStringTaintStep(DataFlow::Node n1, DataFlow::Node n2) {
  stringStep(n1, n2) or assignStep(n1, n2)
}
