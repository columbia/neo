import cpp
import semmle.code.cpp.dataflow.new.DataFlow

/**
 * Predicate to match function calls based on regex patterns (C++)
 */
predicate customizeOp(DataFlow::Node sink) {
  exists(FunctionCall call |
    sink.asExpr() = call.getAnArgument() and
    (
      {{REGEX_PATTERNS}}
    )
  )
}
