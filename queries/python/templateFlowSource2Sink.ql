/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id python/flow-source-sink
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.Concepts
import semmle.python.dataflow.new.RemoteFlowSources
import semmle.python.dataflow.new.BarrierGuards
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
  
  // predicate isBarrier(DataFlow::Node node) {
  //   none()
  // }
  
  //   predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
  //   outBoundTaintStep(node1, node2)
  //   }
}

module MyFlow = TaintTracking::Global<MyConfig>;

// CRITICAL: This import is required for path-problem queries
import MyFlow::PathGraph

// For path-problem queries, you need these specific result patterns:
from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
   "Data from $@ flows to privileged sink.", 
  source.getNode(), "user input"