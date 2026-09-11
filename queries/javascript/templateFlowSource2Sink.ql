/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id javascript/flow-source-sink
 */

import javascript
import DataFlow
import semmle.javascript.dataflow.TaintTracking
import libSource
import libSink
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
}

module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "Data from $@ flows to privileged sink.",
  source.getNode(), "user input"
