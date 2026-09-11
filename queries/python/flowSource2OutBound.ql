/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id neo
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.Concepts
import semmle.python.dataflow.new.RemoteFlowSources
import semmle.python.dataflow.new.BarrierGuards

import libSource
import libOutBound

module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source) // if you have custom sources
  }
  
  predicate isSink(DataFlow::Node sink) {
    // outbound inter-service transmission (HTTP client / gRPC / Kafka / MQ / …)
    outBoundSink(sink)
  }
  
  // predicate isBarrier(DataFlow::Node node) {
  //   none()
  // }
  
  // predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
  //   // Add custom flow steps if needed
  //   // outBoundTaintStep(node1, node2)
  // }
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