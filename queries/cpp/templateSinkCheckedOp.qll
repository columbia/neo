import cpp
import semmle.code.cpp.dataflow.new.DataFlow

predicate checkedOp(DataFlow::Node sink) {
  exists(FunctionCall call |
    sink.asExpr() = call.getAnArgument() and
    {{CALLSITE_CONDITIONS}}
  )
}
