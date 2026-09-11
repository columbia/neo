import csharp
import semmle.code.csharp.dataflow.DataFlow

// Configuration: set to true to include inheritance hierarchy
predicate includeInheritance() { any() }

// C# will replace the placeholder below
predicate checkedOp(DataFlow::Node sink) {
  exists(MethodCall call |
    sink.asExpr() = call and
    {{CALLSITE_CONDITIONS}}
  )
}
