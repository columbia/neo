/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id javascript/flow-source-outbound
 */

import javascript
private import semmle.javascript.dataflow.TaintTracking
import libSource
import libOutBound

module Config implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }

  predicate isSink(DataFlow::Node sink) {
    outBoundSink(sink)
  }

  // Enable taint tracking through property reads, string operations, etc.
  predicate isAdditionalFlowStep(DataFlow::Node pred, DataFlow::Node succ) {
    // Property reads on tainted objects
    exists(DataFlow::PropRead read |
      pred = read.getBase() and
      succ = read
    )
    or
    // String concatenation
    exists(AddExpr add |
      add.getAnOperand() = pred.asExpr() and
      succ.asExpr() = add
    )
    or
    // Template literals
    exists(TemplateLiteral tl |
      pred.asExpr() = tl.getAnElement() and
      succ.asExpr() = tl
    )
    or
    // Value written into an object / array literal taints the literal itself
    // (e.g. axios.post(url, { role: tainted }))
    exists(DataFlow::ObjectLiteralNode obj |
      pred = obj.getAPropertyWrite().getRhs() and succ = obj
    )
    or
    exists(DataFlow::ArrayLiteralNode arr |
      pred = arr.getAnElement() and succ = arr
    )
  }
}

module Flow = TaintTracking::Global<Config>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
  select sink.getNode(), source, sink,
   "Data from $@ flows to privileged sink.", 
  source.getNode(), "user input"


