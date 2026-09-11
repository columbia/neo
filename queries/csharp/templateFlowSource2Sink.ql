/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id csharp/flow-source-sink
 */

import csharp
import semmle.code.csharp.dataflow.DataFlow
import semmle.code.csharp.dataflow.TaintTracking
import semmle.code.csharp.security.dataflow.flowsources.Remote
import libSource
import libSink
{{IMPORT_PLACEHOLDER1}}
{{IMPORT_PLACEHOLDER2}}

module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    enhancedSink(sink)
    // or customizeOp(sink)
    {{SINK_PLACEHOLDER1}}
    // or checkedOp(sink)
    {{SINK_PLACEHOLDER2}}
  }
}

module MyFlow = TaintTracking::Global<MyConfig>;

import MyFlow::PathGraph

from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to privileged sink.",
  source.getNode(), "user input"
