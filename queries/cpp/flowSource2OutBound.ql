/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id cpp/flow-source-outbound
 */

import cpp
import libSource
import libOutBound
import libStringTaint
import semmle.code.cpp.dataflow.new.TaintTracking

module Config implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    outBoundSink(sink)
  }

  predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
    outboundTaintStep(node1, node2) or cppStringTaintStep(node1, node2)
  }
}

module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to outbound sink.",
  source.getNode(), "user input"
