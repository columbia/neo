import go
import semmle.go.dataflow.DataFlow

// Configuration: set to true to include method inheritance
predicate includeInheritance() { any() }  // Change to none() for exact matching only

/**
 * Predicate to match specific callsites based on function targets.
 * This is a template - the {{CALLSITE_CONDITIONS}} placeholder will be
 * replaced by your Python script with actual function matching conditions.
 */
predicate checkedOp(DataFlow::Node sink) {
  exists(DataFlow::CallNode call |
    sink = call.getAnArgument() and
    {{CALLSITE_CONDITIONS}}
  )
}