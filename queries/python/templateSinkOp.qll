import python
import semmle.python.dataflow.new.DataFlow

/**
 * Predicate to match method calls based on regex patterns
 */
predicate customizeOp(DataFlow::Node sink) {
  exists(Call call |
     sink.asExpr() = call  and (
      {{REGEX_PATTERNS}}
    )
  )
}