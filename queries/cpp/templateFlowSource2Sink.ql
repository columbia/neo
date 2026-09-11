/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id cpp/flow-source-sink
 */

import cpp
import libSource
import libSink
import libStringTaint
import semmle.code.cpp.dataflow.new.TaintTracking
{{IMPORT_PLACEHOLDER1}}
{{IMPORT_PLACEHOLDER2}}

module Config implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    enhancedSink(sink)
    {{SINK_PLACEHOLDER1}}
    {{SINK_PLACEHOLDER2}}
  }

  predicate isAdditionalFlowStep(DataFlow::Node n1, DataFlow::Node n2) {
    cppStringTaintStep(n1, n2)
  }
}

module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to privileged sink.",
  source.getNode(), "user input"
