/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id csharp/flow-source-outbound
 */

import csharp
import semmle.code.csharp.dataflow.DataFlow
import semmle.code.csharp.dataflow.TaintTracking
import semmle.code.csharp.security.dataflow.flowsources.Remote
import libSource
import libOutBound

module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    outBoundSink(sink)
  }
}

module MyFlow = TaintTracking::Global<MyConfig>;

import MyFlow::PathGraph

from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to outbound call.",
  source.getNode(), "user input"
