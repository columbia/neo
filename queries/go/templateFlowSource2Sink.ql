/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id go/flow-source-sink
 */

import go
import libSource
import libSink
import semmle.go.dataflow.TaintTracking
{{IMPORT_PLACEHOLDER1}}
{{IMPORT_PLACEHOLDER2}}

module Config implements DataFlow::ConfigSig {
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

  // predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
  //   none()
  // }
}

module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to privileged sink.",
  source.getNode(), "user input"