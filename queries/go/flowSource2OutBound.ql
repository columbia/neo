/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id go/flow-source-outbound
 */

import go
import libSource
import libOutBound

module Config implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    outBoundSink(sink)
  }

  // predicate isBarrier(DataFlow::Node node) {
  //   none()
  // }

  // Add custom flow steps (used by both DataFlow and TaintTracking)
  predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
    outboundTaintStep(node1, node2)
  }
}

// Use TaintTracking instead of DataFlow to handle pointer-based assignments
module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to outbound sink.",
  source.getNode(), "user input"