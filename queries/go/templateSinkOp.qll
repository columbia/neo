import go
import semmle.go.dataflow.DataFlow

/**
 * Predicate to match function calls based on regex patterns
 */
predicate customizeOp(DataFlow::Node sink) {
  exists(DataFlow::CallNode call, Function f |
    call.getTarget() = f and
    sink = call.getAnArgument() and
    (
      {{REGEX_PATTERNS}}
    )
  )
}