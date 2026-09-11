import javascript
import DataFlow

/**
 * Predicate to match specific callsites based on their locations
 */
predicate checkedOp(DataFlow::Node sink) {
  exists(DataFlow::CallNode call |
    sink = call.getAnArgument() and
    {{CALLSITE_CONDITIONS}}
  )
}
