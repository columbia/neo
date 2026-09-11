import javascript
import DataFlow

/**
 * Predicate to match function calls based on regex patterns
 */
predicate customizeOp(DataFlow::Node sink) {
  exists(DataFlow::CallNode call |
    sink = call.getAnArgument() and
    {{REGEX_PATTERNS}}
  )
}
