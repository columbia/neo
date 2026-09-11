import java
import semmle.code.java.dataflow.DataFlow

/**
 * Predicate to match method calls based on regex patterns
 */
predicate customizeOp(DataFlow::Node sink) {
  exists(MethodCall call |
  sink.asExpr() = call and
    {{REGEX_PATTERNS}}
  )
}